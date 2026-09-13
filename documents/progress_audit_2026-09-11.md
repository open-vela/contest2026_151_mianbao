# 项目进度审计（2026-09-11）

> 审计时间：2026-09-11
> 审计人：AI Assistant
> 背景：距 9 月 20 日提交截止仅剩 **9 天**；项目自 2026-07-27 起停摆 **46 天**，重启前做一次全量盘点。
> 用途：作为冲刺期工作清单与交接记录。组员提交成果后，直接在本文档更新状态。

---

## 一、项目概览

**AI 模拟面试官**（队伍 mianbao / contest2026_151）——端云一体的硬件作品。

| 项目 | 内容 |
|------|------|
| 端侧平台 | R528（DshanPI openvela Devkit / T113S3），openvela (dev-ai-contest-2026) |
| 主链路 | 按键触发 → 端侧录音 → 云端 ASR → LLM（小米 MIMO）→ TTS → 端侧播放 |
| 交互 | K1 开始面试 / K2 取消返回 / K3 切换模式；LED1、LED2 状态指示 |
| 云端 | Flask + 小米 MIMO API（ASR / LLM / TTS） |
| 团队 | 4 人分工：A 系统集成 / B 端侧状态机 / C 云端能力 / D Skill 与 Prompt |

---

## 二、时间线：开发在 7/27 停止

```
7/07  初始骨架（liujinye）
7/09  项目目录结构 + 开发情况说明
7/12  云端接入小米 MIMO，5 个 Skill 初始化
7/13  硬件烧录验证通过；Web 界面
7/14  代码实现状态检查报告（当时评估整体约 60%）
7/15  核心功能 + 云端服务
7/17  issue 模板（liujinye）
7/24  按键检测 / LED 控制 / GPIO 配置   ← 最后一次功能提交
7/27  AI 日志更新                        ← 之后停摆
  ⋯⋯ 46 天空白 ⋯⋯
9/11  本次审计（仅日志 manifest 有改动）
```

---

## 三、各模块实际完成度

| 模块 | 状态 | 依据 |
|------|------|------|
| 云端服务 | ✅ ~90% | `cloud/app.py`、`asr_service.py`、`tts_service.py`、`llm_service.py`、`session_manager.py` 齐全 |
| Skill Prompt | ✅ 100% | `skills/` 下 5 个 json 完整 |
| 端侧 GPIO / 按键 / LED | ✅ 7/24 刚完成 | `state_machine.c:99,110` 已是真实 `ioctl` GPIO 读写，不再是打印桩 |
| 端侧状态机逻辑 | ✅ 逻辑完整 | 状态转换 + LED 闪烁效果均已实现 |
| **端侧网络通信** | ❌ **0%** | `network_client.c:16,23,32` 三个函数全是 TODO，无任何实现 |
| **端侧主循环串联** | ❌ **~30%** | `main.c:134-137` 四个 TODO：静音检测 / 录音超时 / 上传回调 / 播放回调 |
| 音频功能 | ⚠️ 有素材未接线 | `app/ai_interview/audio/` 下 aplay/arecord/common/wav_parser 系从 vela-opensource 复制，但**未写入 Makefile 的 `CSRCS`**，当前是死代码 |

**结论：云端基本就绪，端侧的"最后一公里"（发得出去、收得回来）完全空白。**

---

## 四、风险与问题清单

按风险从高到低排列，编号供后续跟踪：

| 编号 | 问题 | 影响 | 位置 |
|------|------|------|------|
| **R1** | **manifest 未映射主应用** | 评委照 README 走 `repo sync` 后**编译不出主程序** | `contest2026_151_mianbao.xml:12-14` 只 linkfile 了 `hello_app` / `hello_quickapp` / `contest_board`；`ai_interview`、`led_test`、`button_test` 依赖 `~/vela-opensource` 里的手动软链 |
| **R2** | **端云链路完全空白** | 云端再完善，端侧发不出去就无法演示 | `app/ai_interview/network_client.c` |
| **R3** | **文档描述了不存在的文件** | 评委会验证，与实际不符 | `documents/project_status.md` 第七节称 7/13 完成 `cloud/templates/index.html`、`WEB_INTERFACE.md`、`start_web.sh`、`test_web.py`——**git 全历史中从未提交过这 4 个文件**，`cloud/static/` 为空目录 |
| **R4** | **README.md 仍是组委会模板** | 评委据此理解作品，模板会导致说明缺失 | 根目录 `README.md`（需按官方要求第六节改写） |
| **R5** | 模板目录残留 | 提交内容不干净 | `logs/your-github-login/` 应删除 |
| **R6** | 今日日志未提交 | 违反日志归集要求 | `logs/xunzhekafei/manifest.json` 已改 + `2026-09-11/` 未跟踪 |
| **R7** | 构建产物混入版本库 | 轻微噪音 | `.built` / `.depend` / `Make.dep` 被 git 跟踪（`.o` 已被 `.gitignore` 正确忽略） |

---

## 五、冲刺建议（优先级从高到低）

1. **补 manifest linkfile（R1）** —— 改动小、风险低、回报最高，是评委复现作品的第一道门。约半天。
2. **打通 `network_client.c`（R2）** —— HTTP POST 音频 / 解析 base64 音频，同时补完 `main.c` 剩余 4 个 TODO。
3. ~~**把 `audio/` 写进 `CSRCS`** —— 让录音 / 播放真正跑起来。~~
   > ⚠️ **此条已于 2026-09-13 证实为错误，切勿执行**：`audio/` 那 6 个文件与 vendor 树
   > `hal/test/sound/` 逐字节相同，而该目录已由 `CONFIG_COMPONENTS_AW_ALSA_UTILS`
   > 编进 `libapps.a`（`nm` 可见 `aplay` / `capture_fs_wav` / `set_param` / `create_wav`
   > 等符号）。再编一份会造成**重复定义**。详见第九节。
4. **端云联调** —— `documents/project_status.md` 原计划的 7/21-7/25 首次联调从未执行，需补齐。
5. **收尾（R3-R7）** —— 修正文档与实现不符之处、重写 README、清理杂项。

---

## 六、状态跟踪表

组员提交成果后逐项更新：

| 项目 | 状态 | 负责人 | 更新日期 | 备注 |
|------|------|--------|----------|------|
| A 同学成果提交 | ⏳ 等待中 | A | | |
| B 同学成果提交 | ⏳ 等待中 | B | | |
| C 同学成果提交 | ⏳ 等待中 | C | | |
| D 同学成果提交 | ⏳ 等待中 | D | | |
| R1 manifest 映射 | ✅ 已完成（未提交） | AI | 2026-09-13 | 4 条 linkfile + 4 个 Make.defs；机制已验证，真实编译待全量 sync |
| R2 网络通信实现 | 🟡 网络层完成（待硬件验证） | AI | 2026-09-13 | 音频链路与主循环串联待做，见第九节 |
| R3 修正文档 | ☐ 未开始 | | | |
| R4 重写 README | ☐ 未开始 | | | |
| R5-R7 清理 | ☐ 未开始 | | | |
| 端云联调 | ☐ 未开始 | | | |
| 最终打包提交（截止 9/20） | ☐ 未开始 | | | |

---

## 七、组员成果到位后需确认的事项

待各方提交后，重点核对以下内容（可能推翻本文档中的部分结论）：

- [ ] 端侧：`network_client.c` 是否已有其他分支 / 未推送的实现？
- [ ] 端侧：音频采集链路（arecord/aplay）是否已在本地验证通过，只是未入库？
- [ ] 云端：Web 界面（`templates/index.html` 等）是否在其他分支或本地存在？
- [ ] 硬件：录音 / 播放 / Wi-Fi 三项验证的真实结论（`project_status.md` 第六节 6.8 验证清单全部空白）
- [ ] 是否有其他成员分支尚未合并到 `dev-ai-contest-2026`

---

**审计完成时间**：2026-09-11
**下次更新**：组员成果提交后

---

## 八、2026-09-13 更新：R1 已修复

**改动**（工作区未提交）：

| 文件 | 改动 |
|------|------|
| `contest2026_151_mianbao.xml` | 新增 4 条 `<linkfile>`，把 `app/ai_interview` / `app/ai_interview_test` / `app/led_test` / `app/button_test` 映射到 `packages/demos/contest2026_151_*` |
| `app/*/Make.defs`（4 个） | `CONFIGURED_APPS` 路径由 `$(APPDIR)/examples/<名>` 同步为 `$(APPDIR)/packages/demos/contest2026_151_<名>` |

**验证结果**：

| 环节 | 方法 | 结果 |
|------|------|------|
| manifest 语法 | 用 repo 自带解析器 `repo manifest` 解析 | ✅ 7 条 linkfile 全部就位 |
| 软链创建 | 按 repo 的形式手工建立 | ✅ 与模板那 3 条同构 |
| Kconfig 注册 | 真实运行 `apps/tools/mkkconfig.sh` | ✅ 4 个应用 Kconfig 均被扫描 |
| 构建路径一致性 | make 模拟 `$(wildcard $(APPDIR)/packages/demos/*/Make.defs)` | ✅ 4 个 `CONFIGURED_APPS` 路径均可达 |
| **真实编译** | — | ❌ **未完成**（需全量 sync，见下） |

**为什么必须同时改 `Make.defs`**：openvela 的应用注册是"Kconfig 扫描目录 + `Make.defs` 声明路径"两段式。目录名对了但 `Make.defs` 路径没跟上时，应用会被**静默跳过编译**——不报错、不警告，产物里就是没有主程序。这是本次改动最大的风险点，已用 make 模拟验证排除。

**新增发现**：

1. **组委会模板自身有同类 bug**：`app/hello_app/Make.defs` 指向 `contest2026_000_hello_app`，而 manifest 映射到 `contest2026_151_hello_app`，两者对不上——模板自带样例应用的路径其实是断的。R1 的修法没有沿用它的写法，因此避开了这个问题。
2. **本地工作区 sync 不完整**：`.repo/projects/` 只有 **13** 个项目（manifest 共 **264** 个），`vendor/allwinnertech` 从未下载 → **本机无法从 repo 工作区编译 R528 固件**。
3. **评委该照哪条命令编译，尚无定论**：README（仍是模板）给的 `./build.sh <board-config-path>` 在 vendor 板子上会失败（`configure.sh` 是相对 `nuttx/` 解析路径的）；而 `documents/project_status.md` 记录的实际流程在**另一棵树** `~/vela-opensource` 里（lichee 环境：`vela_env.sh` + `lunch_nuttx` + `m` + `pack`）。R4 重写 README 时必须给出定论。

**遗留**：真实编译验证需要一次全量 `repo sync`（264 个工程，GB 级、需联网）。

---

## 九、2026-09-13 更新：R2 第一阶段（网络层）完成

按"先网络层、再音频"的节奏推进。本轮把端侧"发不出去"这一环补上了。

### 9.1 改动

| 文件 | 改动 |
|------|------|
| `app/ai_interview/network_client.h` | **新增**：错误码、`cloud_request_t` / `cloud_response_t`、五个函数原型 |
| `app/ai_interview/network_client.c` | **重写**：libcurl POST/GET + cJSON 解析 + mbedtls base64 解码 |
| `app/ai_interview/app_config.h` | **新增**：Kconfig 宏的 `#ifndef` 兜底 + `getenv("CLOUD_URL")` 运行时覆盖 |
| `app/ai_interview/Kconfig` | `STACKSIZE` 8192→32768；新增 worker 栈、云地址、角色、录音上限、静音阈值 |
| `app/ai_interview/Makefile` | 补 curl / mbedtls 头文件路径 |

`CMakeLists.txt` 无需改动 —— CMake 路径已由 `NUTTX_INCLUDE_DIRECTORIES` 全局注入这两条路径（`external/curl/CMakeLists.txt:39`、`apps/crypto/mbedtls/CMakeLists.txt:131`）。

### 9.2 关键发现：云端失败时**没有任何字段**能表示失败（已实测）

用真实 WAV 向本地 Flask 发一次请求（**不带** `MIMO_API_KEY`），实测响应：

```
HTTP 200
type: "question"          ← 不是 "error"
next_action: "continue"   ← 正常值
text: "抱歉，生成问题失败，请重试。"   ← 兜底文案
tts_audio: (空字符串)      ← 唯一能识别失败的字段
```

**结论**：端侧若只看 HTTP 状态码或 `type`/`next_action`，会把失败当成功 —— 演示时表现为"灯正常、没有声音"，极难排查。因此"空的 `tts_audio` 判为失败"不是防御性编程，而是**唯一可靠的检测手段**。判定逻辑单点收敛在 `cloud_parse_response()` 内，三重防线：

1. HTTP 非 2xx → `CLOUD_ERR_HTTP`
2. `tts_audio` 缺失/空串 → `CLOUD_ERR_EMPTY_TTS`
3. 解码后非 WAV（校验 RIFF/WAVE 魔数）→ `CLOUD_ERR_BAD_AUDIO`

### 9.3 验证结果（PC 端单测，不依赖硬件）

把**真实的 `network_client.c`** 与树里的 cJSON、mbedtls base64 一起编译，不打桩：

| 用例 | 期望 | 结果 |
|------|------|------|
| 正常响应 | `CLOUD_OK`，解出完整 WAV | ✅ 48044 字节，RIFF/WAVE 魔数正确 |
| **空 `tts_audio`（实测抓取的真实响应）** | `CLOUD_ERR_EMPTY_TTS` | ✅ |
| 服务端 `error` 结构 | `CLOUD_ERR_EMPTY_TTS` | ✅ |
| 非 JSON（HTML 错误页） | `CLOUD_ERR_JSON` | ✅ |
| 空 body / NULL 入参 / 重复 free | 不崩、返回错误码 | ✅ |

AddressSanitizer + LeakSanitizer 全程无泄漏、无越界。

### 9.4 踩到的坑（已修）

**失败路径的内存归属**：初版在返回错误码前已经分配了 `text`/`user_text`，调用者忘记 free 就会逐轮累积泄漏。已改为失败时模块内部统一释放并归零 `resp`，使**调用者无论成败都可安全调用 `cloud_response_free()`**。

### 9.5 仍缺什么才能演示

| 缺什么 | 说明 |
|--------|------|
| **`MIMO_API_KEY`** | 环境变量未设置；git 历史里那个 key（commit `812a1b5`）**已泄露到远端仓库，演示前应轮换** |
| **云端部署地址** | 尚未确定。端侧已做成 Kconfig + `nsh> set CLOUD_URL ...` 运行时覆盖，换地址不必重编重烧 |
| **音频链路** | 第二阶段：录音到内存 + 静音检测 + 播放 |
| **`main.c` 主循环串联** | 第二阶段：4 个 TODO + 工作线程（网络/音频都是秒级阻塞，不能放主循环） |
| **真实编译验证** | 依赖全量 `repo sync`（进行中） |

### 9.6 依赖现状（本阶段零 defconfig 改动）

选型时刻意避开了需要改板级 defconfig 的方案，因为 **defconfig 在 `vendor/allwinnertech/` 里，不在本仓库，评委 sync 不到**：

| 能力 | 来源 | 是否需改 defconfig |
|------|------|-------------------|
| HTTP | `CONFIG_LIB_CURL`（R528 defconfig 已开） | 否 |
| base64 | `mbedtls_base64_*`（由 LIB_CURL 间接引入，已链接） | 否 |
| JSON | `CONFIG_NETUTILS_CJSON`（已开） | 否 |

> 注：`apps/netutils/codecs` 的 `base64_encode` 需要 `CONFIG_CODECS_BASE64`，该配置**未开且不在本仓库内**，故弃用。
