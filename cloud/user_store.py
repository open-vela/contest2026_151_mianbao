"""账号与绑定 token（2026-10-27 加，产品化 P2 的第一步）。

为什么先做"扫码绑定"而不是完整的账号密码体系
--------------------------------------------
练习机的使用场景是"公共设备、个人账号"：用户不需要注册密码，扫一下设备上的
二维码，在手机上填个昵称，这场及以后的记录就归到他名下。密码体系会带来找回、
重置、泄露等一堆问题，而这个场景不需要——**token 即身份**。

模型（刻意最小）
----------------
* **绑定 token**：设备启动时向云端申请，显示成二维码。手机扫码打开 `/bind`，
  填昵称后 token 与用户绑定。**token 同时就是设备的长期凭据**（设备把它存到
  `/data/ai_interview_user`，之后每次请求都带上）——这样设备不需要轮询"绑定
  完成没有"，实现简单；代价是"谁先扫到二维码谁就是账号主人"，演示场景可接受。
* **用户**：id（uuid）、昵称、可选手机号、创建时间。没有密码。
* 存储：`cloud/data/users/users.json`，原子写（同 session_store 的取舍：
  写失败只记日志，不影响调用方）。

隐私：昵称/手机号只存在本地磁盘，不对外展示；手机号可选，不强制。
"""
import json
import logging
import os
import secrets
import time
import uuid

logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "users")
STORE_PATH = os.path.join(DATA_DIR, "users.json")

NICKNAME_MAX = 24
TOKEN_LEN = 24              # token_urlsafe 的字符数（约 144 bit 熵）


def _load() -> dict:
    try:
        with open(STORE_PATH, encoding="utf-8") as fp:
            data = json.load(fp)
    except FileNotFoundError:
        return {"users": {}, "tokens": {}}
    except Exception as error:          # noqa: BLE001 —— 坏文件当空库，不炸服务
        logger.warning(f"[账号] 读取 {STORE_PATH} 失败，按空库处理：{error}")
        return {"users": {}, "tokens": {}}
    if not isinstance(data, dict):
        return {"users": {}, "tokens": {}}
    data.setdefault("users", {})
    data.setdefault("tokens", {})
    return data


def _save(data: dict) -> None:
    """原子写：临时文件 + os.replace。失败只记日志（同 session_store）。"""
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        tmp = STORE_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fp:
            json.dump(data, fp, ensure_ascii=False, indent=1)
            fp.flush()
            os.fsync(fp.fileno())
        os.replace(tmp, STORE_PATH)
    except Exception as error:          # noqa: BLE001
        logger.warning(f"[账号] 保存 {STORE_PATH} 失败（不影响本次调用）：{error}")


def create_token() -> str:
    """申请一个绑定 token（设备用；尚未绑定用户）。"""
    data = _load()
    token = secrets.token_urlsafe(TOKEN_LEN)
    data["tokens"][token] = {"created_at": time.time(), "user_id": ""}
    _save(data)
    return token


def bind(token: str, nickname: str, phone: str = ""):
    """把 token 绑定到（新建或已有的同名？不——每次绑定新建用户）用户。

    返回用户 dict；token 不存在/已被别人绑定时返回 None。
    重复绑定同一 token：**沿用已绑定的用户**（幂等），避免手机刷新页面时
    给同一个人建出两个账号。
    """
    token = (token or "").strip()
    nickname = (nickname or "").strip()
    phone = (phone or "").strip()

    if not token or len(token) > 128:
        return None
    if not nickname or len(nickname) > NICKNAME_MAX:
        return None
    if phone and (len(phone) > 20 or not phone.replace("-", "").replace("+", "").isdigit()):
        return None

    data = _load()
    record = data["tokens"].get(token)
    if record is None:
        return None

    user_id = record.get("user_id") or ""
    if user_id and user_id in data["users"]:
        return data["users"][user_id]          # 幂等：同一 token 重复绑定

    user_id = str(uuid.uuid4())
    user = {
        "id": user_id,
        "nickname": nickname,
        "phone": phone,
        "created_at": time.time(),
    }
    data["users"][user_id] = user
    record["user_id"] = user_id
    record["bound_at"] = time.time()
    _save(data)
    logger.info(f"[账号] 绑定成功 token={token[:6]}… user={user_id[:8]}…")
    return user


def user_for_token(token: str):
    """token → 用户（未绑定返回 None）。设备每次请求都用它。"""
    token = (token or "").strip()
    if not token:
        return None
    data = _load()
    record = data["tokens"].get(token)
    if not isinstance(record, dict):
        return None
    user_id = record.get("user_id") or ""
    user = data["users"].get(user_id) if user_id else None
    return user if isinstance(user, dict) else None


def user_for_id(user_id: str):
    """用户 id → 用户（网页 cookie 用）。"""
    user_id = (user_id or "").strip()
    if not user_id:
        return None
    data = _load()
    user = data["users"].get(user_id)
    return user if isinstance(user, dict) else None


def token_of_user(user_id: str):
    """用户 id → 它绑定的 token（只给调试/测试用；不要对外暴露）。"""
    data = _load()
    for token, record in data["tokens"].items():
        if isinstance(record, dict) and record.get("user_id") == user_id:
            return token
    return None
