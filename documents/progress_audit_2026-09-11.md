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
| R1 manifest 映射 | ✅ 已完成（已提交） | AI | 2026-09-13 | 4 条 linkfile + 4 个 Make.defs；机制已验证，真实编译待全量 sync |
| R2 网络通信实现 | ✅ 已完成并上板验证 | AI | 2026-09-13 | 见第九、十节 |
| R3 修正文档 | ✅ 已完成（9/14） | AI | 2026-09-14 | `project_status.md` §七/§八/§四、`cloud/README.md`、集成测试程序输出，详见 §11.10 |
| R4 重写 README | ✅ 已完成（9/14） | AI | 2026-09-14 | 编译命令定论见 §11.9 |
| R5-R7 清理 | ✅ 已完成（9/14） | AI | 2026-09-14 | 模板日志目录、12 个构建戳、2 个测试音频；详见 §11.11 |
| 端云联调 | ✅ 已完成（9/13 上板跑通） | AI | 2026-09-13 | 见第十一节 |
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
3. ~~**评委该照哪条命令编译，尚无定论**：README（仍是模板）给的 `./build.sh <board-config-path>` 在 vendor 板子上会失败（`configure.sh` 是相对 `nuttx/` 解析路径的）~~ —— **此结论已于 2026-09-14 推翻，见 §11.9**。`./build.sh <board-config-path>` 在 vendor 板子上**可用**（这正是厂家 `m`/`mnsh` 内部调用的同一条命令），当时"会失败"的判断来自对 `configure.sh` 路径回退链的误读。

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
| ~~**`MIMO_API_KEY`**~~ | ✅ 已配好并实测有效（见 9.7）。注意：该 key 在 git 历史（commit `812a1b5`）里**已泄露到远端仓库，演示前应轮换** |
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

### 9.7 云端契约实测（V1，已用真实 key 打通）

本地起 Flask（`python3 cloud/app.py`，监听 `0.0.0.0:5000`）后发真实请求，**全链路成功**：

| 观测项 | 实测值 |
|--------|--------|
| HTTP 状态 | 200 |
| **单轮端到端耗时** | **22.2 秒** |
| ASR 识别 | 正确（`user_text` 字段可用） |
| LLM 回复 | 正常返回面试官追问 |
| `tts_audio` | 532540 字符 base64 → 解码 399404 字节 |

**TTS 音频格式实测确认**：`PCM(1) / 单声道 / 24000Hz / 16bit`，**带完整 44 字节 WAV 头**。

> ⚠️ `documents/api_protocol.md:24` 写的是"base64 编码的 **PCM** 音频" —— 不准确。
> 端侧若按裸 PCM 直接送 DAC，会把 44 字节文件头当噪声播出来。**按 WAV 解析**。

**⚠️ 22 秒是一个必须在演示脚本里正视的数字**：用户说完话到听见回应要等 22 秒。
端侧 `STATE_UPLOADING` 的 LED 慢闪正好覆盖这段等待，是必要的体验补偿 —— 音频
实现时不要把它简化掉。若现场网络更慢，`CURLOPT_TIMEOUT` 已给到 120 秒。

---

## 十、2026-09-13 更新：R2 第二阶段（音频 + 主循环）完成，全链打通

### 10.1 改动

| 文件 | 改动 |
|------|------|
| `app/ai_interview/audio_io.h/.c` | **新增**：录音到内存 + 播放 |
| `app/ai_interview/main.c` | **重构**：主循环只做按键/LED/排空事件；三段阻塞流水线移入工作线程 |
| `app/ai_interview/Makefile` | `CSRCS` 加 `audio_io.c`，补 vendor ALSA 头路径（hal + osal） |
| `app/ai_interview/app_config.h` | 补 `WORKER_STACKSIZE` 兜底 |

### 10.2 音频实现的关键取舍

**复用而非重写**：`set_param` / `pcm_read` / `pcm_write` 直接用 `libapps.a` 里 vendor
那份（那段 ALSA hw/sw params 序列在真机验证过，重写风险高）。本模块只通过
`audio/common.h` **声明引用**，不重复编译 —— 那 6 个 `.c` 与 vendor 树逐字节相同，
再编一份会造成重复定义（见 9.1 的警告）。WAV 头的读写自己做（44 个固定字节，
比依赖 `wav_header_t` 的结构体对齐假设更稳）。

录音参数 16kHz / 单声道 / 16bit，100ms 分块（与主循环节拍一致），带三级护栏：
静音 2 秒收尾、最短人声 300ms（防开头气声被截断）、5 秒无人声则不上传。

### 10.3 并发模型（为什么必须分线程）

单轮上传实测 **22 秒**。若放在主循环里做，LED 会僵住 22 秒、按键全部失灵 ——
而 LED 慢闪是"系统还在工作"的唯一反馈。

```
主线程    按键扫描 + LED 刷新 + 排空事件队列（100ms 节拍）
工作线程  录音 -> 上传 -> 播放（栈 262144）
```

**硬约束：`state_machine` 只由主线程调用。** 它全程无锁（read-modify-write +
GPIO ioctl + 闪烁计数器），多线程投递会丢状态、LED 交错。工作线程只往事件
队列投事件。因此 **`state_machine.c` 零改动**，B 同学的代码不受影响。

另一个隐蔽竞态：**投递 `EVENT_PLAY_DONE` 必须是工作线程的最后一条语句**（在
所有 `free` 之后）。否则主线程收到后转 IDLE，用户立刻按 K1 开下一轮，会与上一轮
的收尾并发。已写进代码注释。

### 10.4 编译期发现并修掉一个"开机即崩"

初版把 `cloud_health_check()` 放在 `main()` 里 —— 而它内部走 curl。**libcurl 需要
200KB 量级的栈**（参考 `CONFIG_EXAMPLES_HTTP_STACKSIZE` 默认 204800），主任务栈
即使提到 32768 也远远不够，表现为开机随机崩溃而非干脆报错。

已把 curl 相关调用全部移入工作线程。**这类问题编译不报错、只有上板才暴露**，
靠的是核对栈需求量级才提前发现。

### 10.5 编译验证（已通过）

在 `~/vela-opensource` 完成真实交叉编译 + 链接：

- `libapps.a` 里可见 `ai_interview_main` / `audio_record_wav` / `audio_play_wav` / `cloud_send_audio`
- `vela_nsh.elf` 里可见 `ai_interview_main`
- 固件二进制里可查到全部新代码字符串（`开始录音`、`工作线程创建失败`、`音频格式不支持` 等）

> 注：ELF 里查不到 `audio_record_wav` 这类独立符号是**正常的** —— 构建开了 LTO，
> 函数被内联后符号名消失（符号表里能看到 `.lto_priv.0` 后缀和 `audio_io.c.<hash>`）。
> 判断代码是否进固件，用二进制里的字符串比查符号可靠。

### 10.6 顺带修掉的一个隐患：编译树与 manifest 布局不一致

R1 把应用从 `apps/examples/` 迁到 `packages/demos/contest2026_151_*` 后，
`~/vela-opensource` 里还是旧的 `apps/examples/` 软链 —— 新路径不存在，应用会被
**静默跳过编译**。已按 manifest 布局重建软链、删除旧链（否则同一应用注册两次），
并用 `mkkconfig` + make 模拟验证 4 个应用都能正确解析。

**教训：manifest 和本地编译树的布局必须一致，改一处就得同步另一处。**

### 10.7 仍未验证的（下一步）

| 项 | 说明 |
|----|------|
| **硬件联调** | 代码从未在板子上跑过。需编译烧录后实测 |
| **Wi-Fi 未连接**（阻塞项） | 板子 `wlan0` 有 UP 但 **IP 是 0.0.0.0**、MAC 全零、RX/TX 计数为 0 —— 完全没联网。`nsh> http` 报 `Couldn't resolve host name` 就是这个原因，不是 libcurl 的问题 |
| **演示网络前提** | 板子与跑 Flask 的机器**必须在同一网段**。若用手机热点，Flask 那台机器也要连同一热点 |
| 评委路径编译 | repo 工作区 sync 不完整（13/264），`build.sh` 路径未验证 |

---

## 十一、2026-09-13 上板联调记录

本节记录**第一次真机联调**的全过程。链路已打通，麦克风问题已定位。

### 11.1 端到端链路已跑通（真机验证）

```
[Cloud] 健康检查 HTTP 200 -> 云端在线          ← 板子↔宿主机↔VM↔Flask 全通
[Cloud] 本轮成功: 1129004 字节 WAV             ← 上传成功，云端返回音频
[Main] 面试官: 您的回答跳出了常规的"产品功能"框架...  ← LLM 真的回复了
[Audio] 开始播放: 24000 Hz / 1 声道 / 23.5 秒   ← 播放成功
[Audio] 播放结束: 成功
```

### 11.2 麦克风问题：两个独立的原因，都已修复

**原因一：模拟输入通路未打开**

现象 `hw_params 失败 (return: -22)`，报错信息是误导性的
`capture only support 1~3 channel`。读 codec 源码后确认，它检查的**不是请求的
通道数**，而是 `sunxi_get_adc_ch()` —— 读 ADC 的 ANA_CTL 寄存器里的
`MIC_PGA_EN`/`FMINL_EN`/`LINEINL_EN` 位，一个都没开就返回 -1。

codec 上电默认不开任何输入路由，启动脚本里也没有 amixer，必须应用自己开。

**原因二：ADC 数字音量未设置**

通路打开后 hw_params 不再报错，但采回来的是**恒定全零**（`RMS≈1`），说话毫无反应。
补上 `ADC1/2/3 digital volume = 255` 后依然如此 —— 说明这是第二个独立问题而非全部。

**根本原因：麦克风根本不在模拟 codec 上**

排查过程（全部用 vendor 的 arecord，与我们的代码无关）：

| 命令 | 结果 |
|------|------|
| `arecord -D default -r 16000 -c 3 -d 5 -t` | 采集正常，**回放失败**（播放只支持 1~2 声道） |
| `arecord -D hw:snddmic -r 16000 -c 2 -d 5 -t` | 采集正常，**回放打不开**（DMIC 是纯采集设备） |
| `arecord -D hw:snddmic ... /data/t2.wav` + `aplay /data/t2.wav` | ✅ **听到声音** |

> ⚠️ **排查陷阱**：`arecord -t`（录完即放）把回放也放在同一个设备上，于是
> "采集通路支持 3 声道、播放通路只支持 1~2 声道"会**伪装成采集失败**，
> 白白带偏一轮排查。**必须采到文件、再用 `aplay` 单独放**。

**结论：这块板子的麦克风接在数字麦（DMIC）上**，设备名 `hw:snddmic`
（`CONFIG_AW_AUDIO_DMIC=y`，`r528_boot.c:818` 注册为 pcm1c）。
`default` 解析到模拟 codec，那条通路上没有麦克风。

### 11.3 修复内容

| 改动 | 说明 |
|------|------|
| 采集设备 | `default` → `hw:snddmic`（仍可用 `nsh> set PCM_DEV` 覆盖） |
| 声道处理 | DMIC 以 2 声道采集，下混成单声道再送 ASR。取平均而非取单路 —— 不确定麦克风落在哪一路 |
| 数字增益 | 默认 ×4。**DMIC 驱动没有任何增益控件**，实测录音偏小，只能在软件里补。可运行期调：`nsh> set MIC_GAIN 8` |
| 静音判定 | 改在下混**后**的数据上做，增益同时作用于判决 |
| codec 配置 | 保留 DAC/HPOUT 音量设置 —— 那部分对**播放**仍然必要 |

### 11.4 下一次上板要做的

1. 烧录含 DMIC 修复的固件（本地 commit `7746f8d`，**尚未推送、尚未烧录**）
2. 按 K1 说话，记录 `本块均方≈` 在**说话时**和**安静时**的数值
3. 据这两个值定 `APP_AI_INTERVIEW_SILENCE_THRESHOLD`（当前 500，按均方比较）
   —— 它直接决定"说完话能否自动停下"：
   - 说话时才 200 多 → 阈值要下调，否则每轮都等满 30 秒
   - 安静时就有 800 → 阈值要上调，否则噪声被当成说话
4. 音量偏小可先用 `set MIC_GAIN 8` / `16` 试，定下来再写进 Kconfig

### 11.5 待办清单（按优先级）

| # | 事项 | 状态 |
|---|------|------|
| 1 | 烧录 DMIC 修复并验证录音 | ✅ 已完成（9/13，端到端跑通） |
| 2 | 定静音阈值与麦克风增益 | ✅ 已完成：增益 **×4**；门限原定 **500**（依据见 11.8），9/14 晚因现场底噪升高改为 **900** —— 见 **§11.19**（⚠️ **新值未重烧到板上**） |
| 3 | 推送未推送的 commit | ✅ 已完成（9/14）：34 个提交已推送至 `openvela/dev-ai-contest-2026`（fork），远端与本机一致（`396c0e8`） |
| 11 | **同步进官方仓**（组员/评委只从官方仓拉，不合并等于拉不到） | ✅ 已完成（9/14 14:03）：**PR #12 已合并**，官方仓前进到 `f3ac722`。注意是 **rebase-merge**，本地分支已同步对齐 —— 见 **§11.15 / §11.16** |
| 12 | 对话展示页（组员要求：网页看对话比串口方便） | ✅ 已完成（9/14）：**只读 + 纯增量**，两个 .py 各删除 0 行；板子链路 11 轮实测未受影响、轮询 295 次 0 失败；宿主机 `127.0.0.1:5000` 访问已由用户实测确认 —— 见 **§11.17** |
| 4 | 复核云端响应 8MB 上限 —— 纯静音那轮触发了 `响应超过上限 8388608 字节` | ✅ 已完成（9/14）：**已正面确认**，共两处越界源（静音轮、报告轮），均已修复并实测 —— 详见 **§11.12** |
| 5 | R3 修正文档（`project_status.md` 描述了 4 个不存在的文件） | ✅ 已完成（9/14）：详见 **§11.10** |
| 6 | R4 重写 README（评委据此复现，**含编译命令定论**） | ✅ 已完成（9/14）：README 已按组委会模板重写；编译命令定论见 **§11.9** |
| 7 | R5-R7 清理（`logs/your-github-login/`、12 个被跟踪的构建产物） | ✅ 已完成（9/14）：共摘除 16 个文件，详见 **§11.11** |
| 8 | 演示排练（多轮对话 + Wi-Fi 稳定性） | ✅ 已完成（9/14，两轮）：第一轮**抓到真 bug**（推理模型思考吃光 token → 报告轮正文为空、用户听到"生成报告失败"），修复后第二轮真机 11 轮全部正常、**报告正常播出** —— 见 **§11.14** |
| 9 | 演示前最后一次轮换 MIMO key（旧 key 已进过远端历史） | ⚠️ 部分完成（9/14）：已确认现用 key 与历史中泄露的旧 key **不是同一个**（旧 key 已不在使用，风险实质解除）；演示前仍建议再轮换一次作最终保险 —— 见 **§11.12** |
| 10 | 上板验证「断电重启后板子会不会自动连回热点」 | ✅ 已完成（9/14）：**确定不会**，每次上电都要手敲四条 `wapi` 命令。后续要自动化须改 vendor defconfig 并**重烧**，团队决定暂缓 —— 见 **11.7** |
| 13 | 面试官「问的问题有出处」：接入面试题库 + 面试方法论 | ✅ 已完成（9/18）：题库 `question_bank/`（2830 题 / 6 个岗位，含可复现导入脚本与出处说明）+ 检索模块 `cloud/question_bank.py`；提示词加【面试纪律】段与参考块注入。PC 端 11 轮校验、单变量 A/B、以及 A/B 抓出的新问题见 **§11.21** |
| 14 | **把「静音门限 900」与「岗位默认值 `AI 应用开发`」合并成一次重烧** | ✅ 已完成（9/18 晚）：**一次烧录把两件同时验掉** —— 板上日志确认 **`门限 RMS 900`**（不再需要 `set` 顶着），云端侧反证岗位默认值已生效（`role=AI 应用开发`）。随后真机跑了**两场完整面试**，报告功能首次在真实 10 轮对话下端到端跑通 —— 见 **§11.22** |

### 11.6 当前环境状态（2026-09-13 晚，已按实测修正）

- **Flask**：`192.168.93.141:5000`，监听 `0.0.0.0`，已配 MIMO API key
  - ⚠️ **key 只存在于该进程内存中** —— 不在 `.bashrc`、不在 `.profile`、无 `.env` 文件。**虚拟机重启即丢失**，恢复方法见 11.7
- **网络方案**：「手机热点 + VMware NAT 端口转发」（宿主机 `172.20.10.2:5000` → 虚拟机 `192.168.93.141:5000`）
  - ~~曾卡在 Windows 防火墙，已放行~~ —— **此结论已推翻**，见 11.7 与 11.8。Windows 防火墙从头到尾都不是原因，**不要**为它加规则
- **板子**：连手机热点（`172.20.10.5`），**固件已是含 DMIC 修复的新版，端到端已验证通过**
- **代理**：`172.25.160.1:7897`，GitHub 可达（HTTP 200）
- **repo sync**：已停止（只同步了 13/264 个项目，速度过慢）

### 11.7 演示日环境恢复手册

> 这一节是给**演示当天**用的：关机重启后照这个顺序恢复。命令均已对着源码与烧录镜像核对过；**没核对过的会明确标注**。

#### 恢复顺序

从外到内。**只有第 4、5 步需要手动做**，其余都是持久的：

| # | 环节 | 重启后要做什么 |
|---|------|----------------|
| 1 | 手机热点 | 打开；演示期间手机别息屏 |
| 2 | Windows 宿主机 | 连上热点。VMware NAT 端口转发是持久配置，不用重配 |
| 3 | 虚拟机 | 开机 |
| 4 | **Flask** | ⚠️ **不会自启，必须手动拉起** —— 见下 |
| 5 | **板子** | ⚠️ 固件在 flash 里，上电即用、**不用重烧**；但 wlan0 要确认 —— 见下 |

#### 第 4 步：拉起 Flask

```bash
cd ~/openvela_contest/contest2026_151_mianbao/cloud
export MIMO_API_KEY="$(sed -n '42p' ~/test-project/README.md | tr -d '\r\n')"
python3 app.py
```

> ⚠️ **`~/.mimo_key` 已不存在**（2026-09-14 更正）—— 手册早期版本写的是 `cat ~/.mimo_key`，**照着敲会失败**。现用 key 只存在于 **`~/test-project/README.md` 的第 42 行**（注意**不是最后一行**，最后一行是个 GitHub handle；也不在 `.bashrc`/`.profile`，无 `.env`）。
>
> 想恢复成"稳定路径"的话（**推荐**，因为 README 第 42 行会随那次项目的日常编辑而漂移）：
> ```bash
> sed -n '42p' ~/test-project/README.md | tr -d '\r\n' > ~/.mimo_key
> chmod 600 ~/.mimo_key
> ```
> 之后手册里的 `cat ~/.mimo_key` 就又能用了。用编辑器而不是 `export`，是为了不让 key 落进 shell history。
>
> ⚠️ **`python3 app.py` 不会打印任何 key 信息**（旧手册写「启动成功时会打印 `API Key: sk-...`」是错的 —— 那句 print 在 `llm_service.py:305` 的 `if __name__ == "__main__"` 里，只有直接跑 `python3 llm_service.py` 才走）。**正确的自检方式是打一发 TTS**（`/api/health` 不校验 key，永远返回 ok，**不能**用它自检）：
> ```bash
> curl -s -X POST http://127.0.0.1:5000/api/test/tts \
>   -H 'Content-Type: application/json' -d '{"text":"演示前自检"}' \
>   | python3 -c "import sys,json; a=json.load(sys.stdin).get('audio',''); print('key OK, '+str(len(a))+' 字符 base64' if a else '⚠️ audio 为空 —— key 没读到')"
> ```
> 实测（2026-09-14）：`HTTP 200`、81980 字符、2.1 秒。
>
> **忘了设的典型症状**：HTTP 200，但端侧报 `tts_audio 为空（云端多半缺 API key）`。见到这条先查 key，别去查网络。

#### 第 4.5 步：确认题库已加载、岗位映射对得上（2026-09-18 新增）

**这就是一条命令**，起完 Flask 敲一次，比读日志快：

```bash
cd ~/openvela_contest/contest2026_151_mianbao/cloud
python3 -c "from question_bank import warmup, normalize_role; b=warmup(); \
print('题库', b['loaded'], b['records'], '题'); \
print('岗位映射 →', repr(normalize_role('AI 应用开发')))"
```

要看到 **`题库 True 2830 题`** 和 **`岗位映射 → 'AI 应用开发'`**。

| 看到的 | 含义 | 怎么办 |
|--------|------|--------|
| `题库 False 0 题` | `question_bank/data/` 不在这台机器上（没拷过来 / 目录被改名） | **当场修**。面试照样能跑，但问题不再来自题库（静默退化，界面上看不出来） |
| `岗位映射 → ''` | 岗位名对不上题库 | 改用题库里的 6 个岗位名或别名表的别名（`README.md` 4.2.2 有表；NSH `set` 的空格陷阱见 4.7） |

> 启动日志里同一信息也有（`[题库] 就绪：2830 道题，岗位：…` / `[题库] 未加载到题目`），但**这条命令是一眼可判的**，而且不用在滚动的日志里找。
>
> **参考题是"改写"不是"照读"**：参考块明确要求模型挑一道贴合的回答、**用自己的话问出来**、禁止照读。所以**不要**拿题库原文去逐字比对面试官的话；判"题库有没有生效"要看它问的**是不是那个方向**（比如岗位是 `AI 应用开发`，问题开始围绕 RAG / 向量检索 / 召回评估转）。

#### 第 5 步：板子 Wi-Fi

上电后第一件事：

```
nsh> ifconfig
```

wlan0 应拿到 `172.20.10.x`。**掉线就手工重连**（数字索引已对着源码核对）：

```
nsh> wapi mode  wlan0 2
nsh> wapi psk   wlan0 <热点密码> 3
nsh> wapi essid wlan0 <热点名>   1
nsh> renew wlan0
```

| 参数 | 值 | 含义（`apps/wireless/wapi/src/wireless.c`） |
|------|-----|------|
| `mode` | `2` | `WAPI_MODE_MANAGED` —— 站点（STA）模式 |
| `psk` | `3` | `WPA_ALG_CCMP` —— WPA2-AES，现代热点的标准选项 |
| `essid` | `1` | `WAPI_ESSID_ON` —— 立即生效，不延迟绑定 |

#### 关掉 Wi-Fi 省电（建议演示前必做）

```
nsh> wapi power_save wlan0 off
```

**为什么**：到今天为止**所有**端到端失败的根因都是同一个 —— **wlan0 掉出了热点**，包括那次被误判成「Windows 防火墙拦截」的"完全连不上"。Realtek 的省电模式是这类随机掉线的头号嫌疑：驱动进省电后可能漏收信标，被 AP 判为离线后踢掉。实测日志里也出现过播放中途重新做 WPA 握手（`RTL871X` 那几行）。

> `wapi_power_save_cmd` 的实现是「参数恰好等于 `on` 才开，其余一律关」，所以写 `off` 一定能关掉（`wapi.c`）。

#### ⚠️ 下面两条命令在本板固件上**不存在**

```
nsh> wapi save_config wlan0     # ← 敲了会报错
nsh> wapi reconnect   wlan0     # ← 敲了会报错
```

它们被 `#ifdef CONFIG_WIRELESS_WAPI_INITCONF` 包着（`wapi.c`），而本板该配置是**关**的：

1. `apps/wireless/wapi/Kconfig`：`config WIRELESS_WAPI_INITCONF` → `default n`
2. 构建树 `nuttx/.config:4594`：`# CONFIG_WIRELESS_WAPI_INITCONF is not set`
3. 烧录镜像 `strings` 复核：`power_save` 出现 1 次，`reconnect` / `save_config` **各 0 次**

> 要启用它们得改 `vendor/allwinnertech/boards/r528/r528s3-velaevb1/configs/nsh/defconfig` 并**整个重烧** —— 该文件在 vendor 树里，**不在本仓库**（评委 sync 不到）。**不值得为它重烧。**
>
> **结论：掉线只能手工重敲那四条命令。** 建议抄一份存在手机里，别指望演示当天现翻文档。

#### 换热点要不要重烧？

`CLOUD_URL` 是**编译期烧进固件**的（`app_config.h`，默认 `http://172.20.10.2:5000`）。iPhone 热点网段固定是 `172.20.10.0/28`，所以现在这个地址是稳的、不用动。

**但换热点就会换网段**（安卓热点一般是 `192.168.x.x`），那时两条路：

- **重烧** —— 慢，但确定
- 运行期覆盖 —— 快，但**至今没在真机上正面验证过**：
  ```
  nsh> set CLOUD_URL http://192.168.43.1:5000
  ```
  代码路径是通的（内置应用确实继承 NSH 环境变量，见 `task_spawn.c:226`），但没人实测过。**演示当天不要把宝押在这条上。**

#### 「上电自动连回热点」—— 结论：**不会**（2026-09-14 实测）

**板子断电重启后不会自动连回热点，每次上电都必须手工敲上面那四条 `wapi` 命令。** 这与下面的配置事实一致（`CONFIG_WIRELESS_WAPI_INITCONF` 为关，没有"存下来下次自动连"这回事，见上文）：

- 实测（9/14 排练）：上电后 `ifconfig` 中 wlan0 未取得 `172.20.10.x`，手工重连后全通。
- **这不是偶发，是确定行为** —— 演示当天请把「上电 → 敲四条命令 → `ifconfig` 确认拿到 `172.20.10.x`」当作固定开场流程，**别指望它自己连上**。

**后续若要完善（团队决定暂缓，因为代价是重烧）**：两条路都要改 **vendor 树里**的 `r528s3-velaevb1/configs/nsh/defconfig` 并整个重烧（该文件不在本仓库，评委 sync 不到）：

1. 打开 `CONFIG_WIRELESS_WAPI_INITCONF`，让 `wapi save_config` / `wapi reconnect` 可用，再配合 `essid` 的持久化；
2. 或在 NSH 启动脚本（rcS）里写死那四条命令 —— ROMFS 是编译进镜像的，所以同样要重烧，不能"只改配置"。

#### 启动 `ai_interview` 前：确认静音门限（2026-09-14 晚新增）

静音门限已按现场底噪从 500 上调到 **900**，源码默认值也改了（`app_config.h` / Kconfig，见 §11.19）。**但这个新默认值要重烧固件才生效** —— 若当天用的是没重烧过的固件，启动应用**之前**先手动设一次：

```
nsh> set SILENCE_THRESHOLD 900
nsh> ai_interview
```

**设完必须自检**：看录音开始时那一行

```
[Audio] 开始录音（静音 2.0 秒自动结束，最长 30 秒，门限 RMS 900）
```

- 打印 **900** → `set` 生效，可以照常演示。
- 打印 **500** → 说明内置应用**没有继承** NSH 环境变量，`set` 这条路在本板走不通，**只能重烧**（`CLOUD_URL` 那条运行期覆盖也是同一个悬案，至今未在真机正面验证 —— 见上文「换热点要不要重烧」）。

> `set` 只在当前 NSH 会话有效，断电即失 —— 和那四条 `wapi` 命令一样，每次上电都要重敲。

#### 万一面试官开始「话痨」（2026-09-15 新增）

**现象**：一轮回复从正常的 100~200 字膨胀到 **400 字以上**，并且带上一整套模板 —— `**判断：提出新问题**` / `理由：` / `新问题：` / `问题设计说明：（表格）` / `下一步：`。这些标题、表格、`**` 都会被 TTS **逐字念出来**。

**为什么会发生**：模型在**抄自己**。它的原始输出被 `session.add_ai_message()` 原样存进 history，下一轮就成了自己的范例 → 越写越长（实测 460 → 570 → 533 → 456 → 424 字，见 §11.20）。

**⚠️ 它不会自己恢复**：一旦被带歪，这个会话剩下的每一轮都会继续被带歪。**别接着往下答**（答得越多，池子越脏）。

**处置**：重启云端拿回空会话，重开一场 ——

```
ps -eo pid,cmd | awk '$2=="python3" && $3=="app.py"'   # 找到 PID（别用 pkill，会连自己的 shell 一起杀）
kill <PID>
```

然后按上面第 4 步重新拉起。板子那边不用动（它下次 K1 会拿到一个空会话）。

#### 仍未验证

- **`wapi power_save wlan0 off` 是否真能消除掉线** —— 关掉之后要连续跑几轮才看得出来。

### 11.8 本轮实测数据与修复验证

#### 静音阈值 500 的依据

| 场景 | 单块 RMS 实测 | 结论 |
|------|--------------|------|
| 安静（不说话） | 最高 **320**（另一轮 381） | 阈值必须高于它 |
| 说话 | **556 ~ 1951**，有效块多在 1000 以上 | 阈值必须低于它 |

**门限 500 落在两段之间，两侧余量都够。** `MIC_GAIN 4` 维持不变。

#### 修掉的两个问题（均已上板验证）

| 问题 | 现象 | 根因 | 修复 |
|------|------|------|------|
| 短语音收不住尾 | 只说"喂喂"却录了 **16.5 秒**（含 8 秒静音） | `speech_chunks` 是累计值，"喂喂"只产生 2 块 < `AI_MIN_SPEECH_CHUNKS`(3)，**两个终止条件都够不着** | 加 `AI_LONG_SILENCE_CHUNKS`(40) 兜底：只要出过人声，静音够长即停 |
| 按键开机误触发 | 开机即打印 `K2 按下` / `K3 按下` | 引脚配的是下拉，悬空读到低电平，而"上次状态"初值假定为 1（松开）→ 假下降沿 | `read_button_initial()` 开机时读实际电平作初值 |

> K2 那个误触发比看起来严重：它会把 `g_abort` 置 1；**若抢在 K1 前面**，状态机会从 IDLE 直接进 RECORDING，而工作线程压根没收到 `CMD_START`，整机就卡在"录音中"。

**验证结果**：同一句"喂喂？你好你好"从 16.5 秒降到 **5.0 秒**；开机假按键行消失。

#### 其他

- 感知到的 `[Main] K2 按下` 等并发错行，根因是 **NuttX 的 stdio 非线程安全**（主线程与工作线程同时 `printf` 到串口）。日志阅读时按此预期。
- 一次误判记录：曾据"抓包看不到任何包"推断 Windows 防火墙拦截 —— **错**，真因是 wlan0 掉线。教训：**先看板子 `ifconfig`，再看宿主机。**

---

### 11.9 R4 编译命令定论（2026-09-14 实测）

> 这一节回答 §八遗留的"评委该照哪条命令编译"。**结论是：组委会模板给的 `./build.sh <board-config-path>` 本身就是对的**，此前"在 vendor 板子上会失败"的判断是**误读源码后的错误结论**（见下"为什么当初判断错了"）。

#### 定论

| 项 | 值 |
|----|-----|
| 工作目录 | openvela 工作区**根目录**（`build.sh` 所在处，即本仓的上一级） |
| 命令 | `./build.sh vendor/allwinnertech/boards/r528/r528s3-velaevb1/configs/nsh/ -e -Wno-error -j32` |
| 板级配置 | `vendor/allwinnertech/boards/r528/r528s3-velaevb1/configs/nsh/`（随 manifest 的 `vendor/allwinnertech` 工程一并 sync） |
| 产出 | `nuttx/nuttx.bin`（可执行固件）；打包成可烧录 `.img` 还需 lichee 的 `pack` |

`-e -Wno-error` 不是可选项：vendor 板级代码在 `-Werror` 下编不过。这条命令**就是厂家 SDK 自己的 `m`/`mnsh`/`mnuttx` 内部调用的形式**（`vendor/allwinnertech/lichee/tools/scripts/envsetup.sh:699,703,751,755`），README 给评委的就是它。

完整可烧录流程（lichee 环境，`pack` 需要 `lunch_nuttx` 导出的环境变量）：

```bash
cd vendor/allwinnertech/lichee
source vela_env.sh && source envsetup.sh
lunch_nuttx r528s3-velaevb1      # 选板
m                                # 内部即调用上面那条 build.sh，再 strip/objcopy 成 nuttx.bin → nsh.fex
pack                             # 打包 → lichee/out/r528s3/velaevb1_nand/rtos_nuttx_..._256Mnand.img
```

#### 证据链（三条独立证据）

| # | 证据 | 结果 |
|---|------|------|
| 1 | **本机实跑**（2026-09-14 02:2x）：`./build.sh vendor/allwinnertech/boards/r528/r528s3-velaevb1/configs/nsh/ -e -Wno-error -j32` | ✅ **EXIT=0**，`LD: nuttx`，产出 `nuttx.bin`；固件内可查到 `ai_interview` 符号与程序名 |
| 2 | **configure.sh 路径解析实测**（非破坏性：不带 `-e` 时它只做解析与比对，不写树） | ✅ 相对路径与绝对路径均返回 `No configuration change.` / **退出码 0**；错误路径按预期退出 3 |
| 3 | **厂家脚本自身**就是同一条命令 | ✅ `envsetup.sh` 的 `mnsh`/`mnuttx`/`m` 全部是 `cd $ROOT_PATH && ./build.sh vendor/allwinnertech/boards/$RTOS_TARGET_CHIPNAME/$RTOS_BOARD_DEVICE/configs/<config>/ ...` |

`configure.sh` 的路径回退链（`nuttx/tools/configure.sh:156-168`）依次尝试：`${TOPDIR}/boards/*/*/<boarddir>/configs/<configdir>` → `${TOPDIR}/${boardconfig}` → **`${boardconfig}` 原样**。第三条即"按调用者给的路径解析"；而 `build.sh` 在 `${ROOTDIR}/${board_config}` 存在时会先把它**转成绝对路径**再传进去（`build.sh:395-401`），所以**只要在工作区根目录调用就一定命中**。

#### 为什么当初判断错了

上一轮只看到回退链的前两条（都相对 `nuttx/` 解析）就下了"会失败"的结论，**漏掉了第三条兜底**（`${boardconfig}` 原样使用），也没注意到 `build.sh` 会先转绝对路径。教训与 §11.8 那条同源：**对构建系统的结论必须实跑，读代码读不出的地方就设计一个非破坏性的实验**（本次用"不带 `-e` 的 configure.sh"做到了零写入验证）。

#### 顺带查出的两个问题（都已处理）

1. **⚠️ `apps/examples/Kconfig` 有 4 条陈旧项，会让 `m` 报假的 "build failed"** —— `ai_interview`/`ai_interview_test`/`button_test`/`led_test` 的 `source` 行仍指向 7 月那批 `apps/examples/` 旧软链（9/13 迁到 `packages/demos/` 后旧软链被删，但该文件是生成物、没再重新生成）。它不影响编译，但会让**最后一步 `make savedefconfig` 失败、`build.sh` 退出码 3**，于是 `mnuttx` 打印 `build nsh failed` —— **固件其实已经编好了**。已用生成器重建该文件（只删掉那 4 条，其余逐字节一致）：
   ```bash
   cd ~/vela-opensource/apps/examples && ../tools/mkkconfig.sh -m "Examples"
   ```
   > 再遇到 `m` 报 build failed 时，**先看 `nuttx/nuttx.bin` 的时间戳**再决定要不要慌。修好后完整跑一遍为 **EXIT=0**。
2. **`build.sh` 每次成功构建都会把 `nuttx/defconfig` 回写进板级 `defconfig`**（`build.sh` 尾部 `make savedefconfig` + `cp`）。本次回写的**唯一差异**是补上了一行 `CONFIG_APP_AI_INTERVIEW_STACKSIZE=8192`（`.config` 里本来就是 8192，但板级 defconfig 此前缺这行；Kconfig 默认值是 32768）。**这行是把已实测通过的配置固化成"下次干净重建也一致"的记录**，故保留。回写后 `nuttx/defconfig` 与板级 defconfig 仍然一致，增量构建路径不受影响。

### 11.10 R3 修正文档（2026-09-14）

R3 的定义是「文档描述了不存在的文件」。实际排查发现是**一类**问题，共 4 处，全部按「以仓库与实测为准」修正：

| # | 位置 | 原文（错） | 事实 | 处理 |
|---|------|-----------|------|------|
| 1 | `documents/project_status.md` §七 全节（7.1–7.9，104 行） | 称已完成「Web 管理界面」，列出 `cloud/templates/index.html`、`cloud/WEB_INTERFACE.md`、`cloud/start_web.sh`、`cloud/test_web.py` | **这 4 个文件在本仓 git 全历史中 0 提交**（`git log --all -- <path>` 全为空）；`cloud/templates/` 不存在，`cloud/static/` 是空目录 | 整节改写为「云端服务现状」：实际接口（`/api/health`、`/api/interview`、`/api/test/{asr,tts}`）、辅助脚本、启动方式，并新增 **7.5 留档更正** |
| 2 | 同上 §八 时间线行 + 「7月13日完成的工作」第 2 条 | 同上，记为 ✅ 完成 | 同上 | 改为 `⚠️ 原型`，并注明「在开发期工作区、未纳入本仓库、后端未落地、不构成本作品功能」 |
| 3 | 同上 §四 技术选型 | 「AI Agent：openvela ai_agent 框架」「通信协议：HTTPS + JSON」 | 全仓 `ai_agent` **0 引用**（`grep -rn` 于 `*.c/*.h/*.py/Kconfig/Makefile`）；实际是**自研状态机**，协议是**局域网明文 HTTP**（`app.run(host='0.0.0.0', port=5000)`） | 分别改为实测的表述 |
| 4 | `app/ai_interview_test/ai_interview_test_main.c` 的 `[TEST 4]` 输出 + `cloud/README.md` | 程序仍打印「网络通信 - 待实现 / 音频采集 - 待集成 / 云端服务 - 待对接」；cloud/README 仍称 LLM 与 session 是「⏳ 骨架代码」、Flask「待完善」 | 三者均已实现并上板验证 | 更新程序输出字符串与文档；`project_status.md` §6.6 的「预期输出」同步改齐 |

**关于第 1、2 条的来龙去脉**：那套浏览器界面**确实存在过**，但它在**仓库外的开发期工作区** `~/test-project/web_frontend/`（同名的 4 个文件在那里，7/13–7/14 的产物），且其 Flask 后端**已不存在**（该目录现在只剩前端 HTML、说明文档、启动脚本与测试脚本；`start_web.sh` 里 `python3 app.py` 指向的文件已丢失，因而本身也跑不起来）。文档当时把「在工作区搭过原型」写成了「仓库里已完成功能」，属于**把仓库外的东西记成仓库内的**。本次**未**把它移植进仓库 —— 作品主交互在开发板上，存档一个未验证的原型只会给评委复现添乱；如需复活应作为独立任务评估。

**连带修正的两处「快照被当成现状」**（同属"文档与实现不符"，但性质是过期而非虚构）：§二 人员分工表（7/9 快照，多个"未完成"项其实早已完成）与 §1.3 目录结构（7/9 骨架图）各加了一行说明，指向 README 与台账作为当前状态来源，避免评委误读。

**方法教训**：用 `git log --all -- <path>` 判定"某文件是否进过仓库"最可靠 —— 工作区里有、历史里没有，就是"从未提交"；本次也验证了**磁盘上可能存在同名文件**（`~/test-project/web_frontend/`），所以「文件不存在于仓库」≠「这项工作没做过」，写结论时必须区分**仓库内 / 仓库外**。

### 11.11 R5–R7 清理（2026-09-14）

三项一次做完，共从版本库摘除 **16 个文件**（工作区文件一律保留，`git rm --cached` 只摘索引）。

| 编号 | 事项 | 处理 | 依据 |
|------|------|------|------|
| **R5** | 组委会模板的示例日志目录 | 删除 `logs/your-github-login/`（`example.jsonl` + 示例 `manifest.json`） | `logs/README.md` 原文：「请替换成你自己导出的真实日志（**删掉示例的 `your-github-login/` 目录**）」——是组委会自己要求的 |
| **R6** | 当日日志未提交 | 已提交（`9/13`、`9/14` 两个会话 + manifest），提交前跑 `redact_secrets.sh --check` 通过 | 日志归集要求 |
| **R7** | 构建产物混入版本库 | 摘除 12 个构建戳 + 2 个测试音频，并在 `.gitignore` 补 6 条规则 | 见下表 |

**R7 逐项依据**（关键：先确认它们都是**产物**而非源码，且 clean 时会被主动删除）：

| 文件 | 由谁生成 | 是否有必要入库 |
|------|----------|----------------|
| `app/*/.built`（4） | `apps/Application.mk:289` 的构建戳目标；`clean` 时 `DELFILE`（:405） | 否 —— 0 字节标记文件 |
| `app/*/Make.dep`（4） | `apps/Application.mk:392` 自动生成（文件头即 `# Gen Make.dep automatically`） | 否 —— 且以 `-include` 引入（:413、`Directory.mk:63`），**缺失不影响构建**；内容还含本机绝对路径 `/home/ubuntu/vela-opensource/...` |
| `app/*/.depend`（4） | `apps/Makefile:211` 的 `depend` 目标产物；`clean` 时删（:230） | 否 —— 0 字节 |
| `cloud/test_tts_output.wav`、`test_tts_stream_output.wav`（2） | `cloud/test_services.py:43,54` 运行后写出，约 300KB×2 | 否 —— 复跑脚本即再生；`cloud/README.md` 目录清单已改为「运行期产物」说明 |

`.gitignore` 用的是**文件名精确匹配**（`.built` / `.depend` / `Make.dep` / 两个 wav 全名），刻意**不用 `*.wav` 通配** —— 免得将来真加了音频 fixture 被误忽略。

**残留（已知、未处理）**：`app/ai_interview_test/` 工作区里有两个 NuttX 展平命名的中间产物
`ai_interview_test_main.c.home.ubuntu.openvela_contest...o`（把本机路径写进了文件名）。它们**未被 git 跟踪**（`*.o` 已在 `.gitignore`），所以不属于「混入版本库」，本次未动；若要以压缩包形式直接交工作区，需另行清理。

### 11.12 云端 8MB 上限：正面确认与修复（2026-09-14，**不需要开发板**）

台账 11.5 #4 的遗留问题（「纯静音那轮触发 `响应超过上限 8388608 字节`，仍未正面确认」）已用**纯云端实验**关闭：在 PC 上启动 Flask、用 `cloud/test_tts_output.wav` 当作候选人回答，对 `/api/interview` 连打 13 次（同一 `session_id`）复现完整的 11 轮面试，全程真实调用 ASR→LLM→TTS。

**两个越界源，均已定位并修复**

| 来源 | 证据（实测） | 处理 |
|------|--------------|------|
| **静音轮**：ASR 返回空 → LLM 自由发挥 → 超长 TTS | 上板记录：`录音完成 30.0 秒` → `响应超过上限 8388608 字节，中止` | `cloud/app.py` 加**空识别短路**：ASR 为空时固定回「抱歉，我没听清，请再说一次。」。实测静音 3 秒 → ASR `''` → 响应体 **170KB（2.08%）**，1.8 秒返回（完整轮约 30 秒） |
| **报告轮**：`generate_feedback` 的提示词不设长度，`max_tokens=1000` | 同一份 20 条历史各跑 3 次：旧提示词 **788 / 1033 / 1119 字** → **8.40 / 11.17 / 12.21 MB**，即上限的 **105% / 140% / 153%**，**3/3 全部越界**（即报告轮不是"可能"撞上限，是必然撞） | `skills/generate_feedback.json` 加 **200 字硬性上限** + `max_tokens` 1000→600。同条件复测：216 / 248 / 201 字 → **2.54 / 2.77 / 2.13 MB（27% / 35%）**，余量 **3.2 倍** |

**端到端演练结果**：11 轮全部 HTTP 200，ASR/LLM/TTS 均正常，第 11 轮（`len(history) >= 20`）返回 `next_action=finish` —— 与代码推导一致。单轮最大 **5.63 MB（70.4%）**，合计 33.21 MB，**无一轮越界**。

**⚠️ 本轮最重要的发现：报告功能不在端侧调用链路上**

演练日志里 `加载 Skill:` 共 11 行，**全部是 `next_question`，`generate_feedback` 一次都没被加载**。原因是端侧 `main.c:124` 只发 `state = "recording_finished"`，而 `generate_feedback` 只在 `llm_service.llm_interview()` 的 `state == "feedback"` 分支里 —— 该分支是**死代码**。第 11 轮那段 454 字的「面试官最终评估」是 `next_question` 在长历史下**自己即兴写的**，`type=report` 只是 `app.py` 按 `next_action` 贴的标签。

结论：**演示时用户听到的结尾是"一次即兴发挥"，不是设计出来的评估报告** —— 这次它写得不错（还带了表格），但没有提示词保证，换个提问顺序就可能退化成一个普通问题。**要不要把报告真正接上是个产品决策，且改的是端侧协议（需要上板验证），因此本次未动**，留待用户定夺。

**附带发现（未修，主链路提示词保持原样）**：`next_question` 的输出同样没有长度约束，在上述「11 次重复同一段话」的病态输入下单轮冲到 5.63 MB；且它有时会把 `**追问理由：**` 这类 Markdown 一起输出，而这段文字是要**被念出来的**。试过收紧提示词，但**收紧后空返回率变高**（会让用户听到「抱歉，生成问题失败」）：

| 变体 | 空返回 | 字数 | Markdown 残留 |
|------|--------|------|----------------|
| 原提示词（`max_tokens=800`） | **0/8** | 40~170 | 有 |
| 格式要求 + 80 字上限（600 / 800） | 1/8 | 20~47 | 无 |
| 仅格式要求（600） | 3/8 | 10~39 | 无 |
| 60 字上限 + 无 Markdown（400） | **3/8** | 9~28 | 无 |

n=8 太小，无法判定空返回是否由提示词引起（0/8 vs 1/8 在噪声内）。**为不影响演示，该实验已 `git checkout` 撤回，`skills/next_question.json` 与 HEAD 一致。** 待办：想改的话先跑 n≥30 的对照（尤其是「仅加格式要求、`max_tokens` 不变」这个单变量）再定。上板实测的正常轮响应体 ≤1.7MB，所以这条不是演示阻塞项。

**MIMO key 现状（11.5 #9 相关）**：现用 key 与 git 历史里那个旧 key **不是同一个**（比对前 16 位 sha256，两者不同；全仓库工作区与历史中都搜不到现用 key）—— 也就是说**泄露的旧 key 已经不在使用中**，风险已实质解除。仍建议演示前按原计划再轮换一次作为最终保险。

**复现实验的方法（下次可直接用）**：`export MIMO_API_KEY="$(sed -n '42p' ~/test-project/README.md | tr -d '\r\n')"` → `python3 app.py` → 用 `demo` 脚本 POST 同一个 `test_tts_output.wav` 到 `session_id` 复用即可（脚本见 `/tmp/rehearsal.py`、`/tmp/compare_report.py`，会话结束会丢，逻辑见上表）。**测完记得 `pkill -f "app[.]py"`**（`pkill -f "python3 app.py"` 会匹配到自己的 shell，返回 144）。

### 11.13 报告功能接上调用链路（2026-09-14，**纯云端，未上板**）

**背景（承接 §11.12 的发现）**：`generate_feedback` 是死代码 —— 端侧只发 `state="recording_finished"`（`main.c:124`），而报告只在 `llm_interview()` 的 `state=="feedback"` 分支，真实链路上不可达，结尾那段「最终评估」实际是 `next_question` 即兴写的。**用户决策：纯云端接上**（不改端侧协议、不重新烧录）。

**做法：把结束判据前移一轮**

关键点是**结束判据本来就是云端自己算的**（`next_question()` 末尾的 `len(history) >= 20`），不是端侧告诉它的 —— 云端在第 11 轮**开始之前**就知道这是最后一轮，只是过去拿这个信息去贴 `next_action=finish` 标签，而没有拿它决定「该出报告还是该出题」。改动就是把这个已知信息用在生成**之前**：

```python
# cloud/llm_service.py
HISTORY_FINISH_THRESHOLD = 20          # 新增：结束判据集中到一处，防止两处漂移

# llm_interview() 的 recording_finished 分支：
if len(history) - 1 >= HISTORY_FINISH_THRESHOLD:
    return generate_feedback(role, history)
return next_question(role, history[:-1], history[-1]["content"])
```

`len(history) - 1` 的来由：`llm_interview()` 收到的 history **含**本轮回答，`next_question()` 收到的**不含**，两者差 1（已写进代码注释，这是最容易改错的地方）。

**对端侧完全透明**：同一个回合、同一个 `next_action=finish`，只有念出来的 text 变了。端侧 `main.c:207-212` 的处理（清空 `session_id`，下次 K1 开新面试）不变 —— **所以本次不需要上板**。

**验证一：离线路由（桩掉 API，零成本）**

| `len(history)` | 加载的 skill | next_action | type |
|---|---|---|---|
| 18 / 19 / 20 | `next_question` | `continue` | question |
| 21 / 22 / 23 | `generate_feedback` | `finish` | report |

**边界与改动前逐格一致**：改动前也是第 10 轮（n=20）判 `continue`、第 11 轮（n=21）判 `finish`，现在仍是这两轮，只是第 11 轮换了内容。脚本 `/tmp/route_check.py`（会话结束会丢，逻辑即上表）。

**验证二：真实 API 11 轮演练（PC，不需要开发板）**

沿用 §11.12 的复现流程（`session_id` 复用 + `test_tts_output.wav`）：11 轮全 HTTP 200，**单轮最大 3.01 MB（37.6%）**，合计 24.41 MB，**0 轮越界**。服务端 skill 加载序列：

```
加载 Skill: next_question      × 10   ← 第 1–10 轮
加载 Skill: generate_feedback  ×  1   ← 第 11 轮
```

改动前这里是 `next_question` × 11、`generate_feedback` × 0。第 11 轮返回 `type=report`、`next_action=finish`，文本是一份**结构化评估报告**（总体评价 / 优点 / 待改进项 / 综合建议），不再是即兴提问。脚本 `/tmp/rehearsal2.py`。

**遗留**：报告受 §11.12 加的 200 字上限约束，念出来约 40 秒（按 5 字/秒估）。**已决定维持现状（9/14）**，不再放宽 —— 若日后仍要放宽字数，须重测响应体（余量当前 3.2 倍，放宽到 300 字约吃掉一半）。另：`state="feedback"` 分支保留为显式覆盖入口，至今仍无调用方。

**⚠️ 本次改动尚未上板验证**：PC 演练用的是「同一段音频重复 11 次」的病态输入，验证的是**路由正确 + 不越界**（§11.13 上表）；「正常答完 11 轮后听到一份像样的报告」只有**演示排练**能覆盖，因此 **11.5 #8 演示排练同时是本改动的端到端验证**，不是可选项。

### 11.14 排练抓到真 bug：推理模型的思考吃掉了正文预算（2026-09-14，已修复+本机验证，**待重新上板**）

**现象**：9/14 演示排练（真机、正常答满 11 轮）—— 前 10 轮全部正常，**第 11 轮报告失败**，用户听到的是兜底文案 `生成报告失败`（正好 6 个字，与日志里 `TTS 文本长度=6` 对上）。日志关键几行：

```
加载 Skill: generate_feedback
LLM 请求: model=mimo-v2.5, 消息数=2
httpx ... 200 OK
LLM 返回: ...            ← 正文为空
TTS: 文本长度=6          ← 用户听到"生成报告失败"
```

**根因：`mimo-v2.5` 是推理模型，`reasoning_tokens` 与正文共用 `max_tokens` 预算**（响应里带 `reasoning_content`，`usage.completion_tokens_details.reasoning_tokens` 非零）。而所有 skill 的 `max_tokens` 当初是按「输出额度」配的（`generate_feedback` 600、`next_question` 800），**没给思考留位置**。历史越长 → 思考越久 → 正文余量越小，最终被挤成 0。

实测数据（用日志重建的 21 条真实长度历史，n=8）：

| 调用 | max_tokens | 空返回 | 被截断 | reasoning 峰值 |
|------|-----------|--------|--------|----------------|
| `generate_feedback` | 600 | 0/8 | **2/8** | **565 / 600（94%）** |
| `next_question`（第 10 轮，消息数 21） | 800 | **1/8** | 1/8 | **801 / 800（100%）** |

**所以这不是报告一个功能的问题，是整条链路每一步都在贴着悬崖跑**：`next_question` 在第 10 轮有 12.5% 概率让用户听到「抱歉，生成问题失败」、25% 概率问题被腰斩。10 轮排练全过是运气。§11.12 把 `max_tokens` 从 1000 降到 600 时才暴露，正是因为**降的是总额度，而思考是不定额的**。

**修复（一处改，全链路生效）**：`cloud/llm_service.py` 的 `call_llm()` 是唯一的咽喉点，给它加上关思考参数 ——

```python
THINKING_DISABLED = {"thinking": {"type": "disabled"}}
# ...
completion = client.chat.completions.create(..., extra_body=THINKING_DISABLED)
```

> `enable_thinking: false` 在本 API 上**被忽略**（`reasoning_tokens` 仍为 388）；只有 `thinking={"type": "disabled"}` 生效（实测 `reasoning_tokens=0`）。

**验证（三条，均通过）**

1. **空/截断归零**：同条件原始调用 n=8 → 空 0/8、截断 0/8、`reasoning_tokens` 全为 0、正文 123~234 字。
2. **真实函数不再走兜底**：`next_question`×6 + `generate_feedback`×3 → 兜底文案 **0/9**。
3. **本机 11 轮端到端回归**：11 轮全 HTTP 200，**单轮最大 3.71MB（46%）**，第 11 轮 `next_action=finish` 且正文是一份结构化评估报告（总体评价/优点/待改进项/综合建议），合计 145 秒。脚本 `/tmp/pc_rehearsal.py`。

**质量对照（关思考未造成可见损失）**：`next_question` 追问依旧自然、更聚焦；`generate_feedback` 报告结构完整、201~224 字。反而思考开启时出现过一次幻觉（把转录格式误判为"复制带入的面试官内容"）。另外报告轮从 16 秒降到数秒。

**顺带解除一个误判**：§11.12 「收紧 `next_question` 提示词会导致空返回率上升，故撤回」的结论**不可信** —— 该实验是在思考吃掉预算的前提下做的，空返回的真实来源是 token 竞争而非提示词。**现在余量已释放，若日后要收紧提示词（例如抑制 `**追问理由：**` 被念出来），可以重新做单变量对照。**

**残留风险（已量化，暂不动）**：`next_question` 提示词里没有长度上限，关掉思考后正文不再被"思考截断"，长度上限随之放开。但在**真实历史**下实测 n=15：正文 112~186 字（中位 152），**要冲破 8MB 需正文超过 836 字，余量 4.7 倍** —— 故本次不动提示词。⚠️ 注意：用「同一段音频重复 11 次」的病态输入曾把单轮推到 380 字 / 3.71MB，而**没有候选人回答**时模型会自说自话到 1345 字 / 14.56MB，说明病态输入下确实能越界，但真实面试不构成阻塞。

**⚠️ 踩坑记录（下次别重犯）**：本机 PC 复现脚本**必须显式传 `state="recording_finished"`**。`cloud/app.py:42` 是 `if audio_base64 and state == "recording_finished"`，少了这个字段会**静默跳过整段 ASR** —— 没有候选人回答进历史，`llm_interview()` 走不到结束判据（永远不出报告），模型还会在无输入下长篇独白。我据此一度误报"关思考导致 3 轮越界 + 报告不出"，**实为脚本缺陷**，不是回归。

**✅ 上板验证通过（2026-09-14，第二次排练，真机正常对话）**

板子会话 11 轮，技能加载序列 `next_question`×10 + `generate_feedback`×1：

| 指标 | 结果 |
|------|------|
| 轮次 | 11 轮全部 HTTP 200（`172.20.10.5`） |
| 第 11 轮 | `generate_feedback` **正文 262 字**、结构完整（`**面试评估报告** / 总体评价 / 优点 / …`），TTS 2.24MB —— **报告正常播出，用户确认听到了** |
| 单轮最大正文 | 233 字（第 10 轮） |
| 兜底文案 / `LLM 调用失败` / `超过上限` | **全日志 0 次** |

即：**推理模型吃 token 的 bug 已闭环** —— 从「报告轮必空」到真机 11 轮零失败。

**剩余唯一未闭环的项**：`wapi power_save wlan0 off` 是否真能消除随机掉线（需连续多跑几轮观察），见 11.7。

---

### 11.15 同步官方仓：PR #12（2026-09-14）

**背景**：组员与评委按 README §4.1 是从**官方仓** `open-vela/contest2026_151_mianbao` 拉的，而官方仓停在 7/27 的 `9dc2eb9`，中间积压 34 个提交 —— 不合并，谁都拉不到 R1–R7 的成果。

**官方仓禁止直接推送**（分支保护：`Changes must be made through a pull request` + 要求 `cla/signature` 检查），所以走 PR：

| 项 | 结果 |
|----|------|
| PR | **[open-vela/contest2026_151_mianbao#12](https://github.com/open-vela/contest2026_151_mianbao/pull/12)** |
| 源 → 目标 | `xunzhekafei:dev-ai-contest-2026` → `open-vela:dev-ai-contest-2026` |
| 合并性 | `MERGEABLE` / **`CLEAN`**（官方分支是本地分支的**祖先**，可快进，无冲突） |
| CLA | ✅ `pass` —— `CLA signed for all 1 contributor(s)`（**早已签过**，此前 8 个 PR 已合并，最近 #11 在 7/27） |
| 规模 | 34 commits · 54 files · **+6682 / −792** |

**⚠️ 合并权在组织者手里**，本队只能发起。**若临近 9/20 仍未合并，需主动去 PR 下催。**

**密钥复核（进官方仓前重做）**：对区间内**新增行**用当前生效 key 精确串匹配 → **0 命中**；`git grep` 全文件快照 → **0 命中**；`sk-` 长串扫描 → 无。另：历史泄露的旧 key 在 `812a1b5`（7/12），**官方仓早已包含**，本次 PR 不新增暴露 —— 这也是那个 key 必须保持停用的原因。

**⛔ 一个判断失误的记录**：我最初提议「把 `openvela.xml` 的 `fetch="../open-vela/"` 改成绝对地址」以便从 fork 拉取。**核实后放弃了**：`openvela.xml` 是组委会给的共享文件，改动会随 PR 进官方仓，若组织者内部走私有镜像，相对路径才是对的 —— **风险不对等，不动**。改用下面零风险的过渡办法。

**过渡期取码办法（组员用，官方仓合并后作废）**：`-u` 地址**必须保持官方**（相对 remote 是按 manifest 服务器地址解析的，换成 fork 会让整个 openvela 基座解析到不存在的 `xunzhekafei/open-vela`），本队仓另行切到 fork 最新：

```bash
cd contest2026_151_mianbao
git remote add fork https://github.com/xunzhekafei/contest2026_151_mianbao.git   # 已存在则跳过
git fetch fork dev-ai-contest-2026
git merge --ff-only fork/dev-ai-contest-2026
```

`--ff-only` 是刻意的：**已用 `git merge-base --is-ancestor` 核实**官方分支确为其祖先，只会快进、不可能丢改动。之后 `repo sync` 对本项目是**空操作**（合并祖先 = Already up to date），不会退回旧代码；但 **`repo sync --force-sync` 会**。README §4.0 已加同样的折叠说明。

**✅ 已合并（2026-09-14 14:03，by xunzhekafei）**，官方仓 `dev-ai-contest-2026` 前进到 `f3ac722`。组员与评委现在按 README §4.1 直接拉即可拿到全部成果，§4.0 的过渡说明随之作废。

---

### 11.16 官方仓是 rebase-merge 合的：必须对齐分支（2026-09-14）

**现象**：PR #12 合并后，官方仓是 `f3ac722`，本机是 `ea5a838` —— **提交信息一致、SHA 不同**，且两边互不为祖先。

**原因**：GitHub 用了 **rebase-merge**，把 35 个提交逐个重放、**全部换了新 SHA**。内容一字未改，但历史成了平行线。

**⚠️ 不改的后果（下次开 PR 时才炸）**：GitHub 会拿本机历史去 diff 官方仓，两边无共同祖先，于是把那 35 个提交显示成一堆"重复改动"并产生冲突，得手工解一遍 —— 偏偏会撞在 9/20 前最不该折腾的时候。

**⚠️ 一个重要更正**：我此前说 PR 卡在 CLA，**是错的**。`cla/signature` 检查 `pass`，注释为 `CLA signed for all 1 contributor(s)` —— 早就签过（这解释了为什么此前已有 8 个 PR 合并成功，最近 #11 在 7/27）。**别再把这个当成风险点。**

**修法**（内容零丢失，已用 tree hash 逐字节证明两边同为 `9c06841b…`）：

```bash
git stash push -m "本会话日志增量" logs/     # 保护正在增长的会话日志
git reset --hard upstream/dev-ai-contest-2026   # → f3ac722
git stash pop
git push --force-with-lease openvela dev-ai-contest-2026
```

对齐后本机 = fork = 官方 = `f3ac722`，官方仓重新成为本机祖先，**下次 PR 恢复成干净的快进**。

**经验**：**只要 PR 是被 rebase/squash 合并的，本地分支就必须立刻对齐，别等下次开 PR 才发现。** 判断方法一句话：`git merge-base --is-ancestor HEAD upstream/<branch>` 不成立、但两边 tree 相同。

---

### 11.17 对话展示页（只读，2026-09-14）

**需求**：组员提出想在网页上看对话内容，比串口方便。

**决定：做，但限定为「只读 + 纯增量」。** 理由是风险可以压到零并可证明，而不是靠"应该没事"：

| 改动 | 内容 |
|------|------|
| `cloud/app.py` | **新增** `GET /`（返回页面）与 `GET /api/history`（只读快照） |
| `cloud/session_manager.py` | **新增** `get_latest_session()` 与 `snapshot()` 两个只读方法 |
| `cloud/static/index.html` | 新文件，单页，无构建、无依赖 |

**`git diff --numstat` 证明：两个 .py 文件各删除 0 行** —— `handle_interview`（板子唯一会调的接口）一行未动。

**三条刻意不做的**：① 网页不加"发消息"输入框（会创建第二个 session、演示时误触就搅乱板子那场）；② 不改 `session_manager` 任何现有方法；③ 不引新依赖、不引外部 CDN（演示现场是手机热点，外网不一定通）。

**⚠️ 一个差点做错的判断**：页面上本打算用 `is_finished` 区分"评估报告"。核实后发现 **`InterviewSession.finish()` 从来没有被任何地方调用过**，`is_finished` 恒为 False —— 若照此实现，会写出一段永远不触发的样式。故不依赖它。

**⚠️ 另一个必须守住的纪律**：**绝不能往 `session.history` 的字典里加字段**（比如给每条消息加时间戳）。history 会被原样送进 LLM 的 `messages` 参数（`llm_service.next_question` 里 `messages = list(history)`），多出来的键可能被 OpenAI SDK 一并序列化发出去。要展示的信息一律在 `snapshot()` 里新建字典。

**验证（4 项，均为实测）**：

| 项 | 结果 |
|----|------|
| 板子链路未受影响 | 11 轮全部 HTTP 200，单轮最大 3.10MB（占上限 39%），**0 失败 / 0 兜底** |
| 网页轮询不阻塞板子 | 期间每 0.5 秒轮询 `/api/history`：**295 次 0 失败**，平均 2.4ms、最大 11.6ms |
| 两条链路内容一致 | 第 1 轮后 2 条、第 11 轮后 22 条，与 `/api/interview` 返回值**逐条对得上** |
| 只读性 | 全程 1 个 session，`session_id` 未变 —— 网页没把会话搞乱 |

**并发结论的依据**：Flask 源码里 `app.run()` 有 `options.setdefault("threaded", True)` —— **Flask 2.3 默认就是多线程**。（我此前在本文件里写过"Flask 是单线程开发服务器"，**那句是错的**，据此产生的担心不成立。）

**顺带修掉的两个前端 bug**：

1. **入场动画挂错位置**：原本挂在 `.row` 上，导致**每次重绘所有历史消息都把动画重放一遍** —— 来一条新消息整屏闪一次。改为挂在 `.row.new`，并把渲染改成**增量追加**（只渲染 `renderedCount` 之后的新消息），已有对话不再重绘。首屏截图里"文字全是半透明"就是这个原因。
2. **`.new` 标记堆积**：追加时不摘上一批的标记，实测会累积成 2 个。虽因 `insertAdjacentHTML` 不重解析已有节点、当前不产生可见影响，但一旦有人写了依赖 `.row.new` 的样式就会中招，已修。

**验证手段**：用 Node 把页面里那段**真实 JS**（非复制品，从 HTML 抽出来）配 DOM 桩直接跑，17 项断言全过，含 XSS 防护（先转义、再把 `**粗体**` 还原成 `<strong>`，顺序不能反）。另有 Firefox 无头截图确认实际渲染。

**✅ 最后一项也验证通过了**：原本担心"宿主机浏览器访问不到虚拟机里的 Flask"（现有转发规则是给板子用的：板子 → `172.20.10.2:5000` → 虚拟机）。**2026-09-14 由用户在 Windows 物理机上实测：`http://127.0.0.1:5000/` 可以正常看到页面和实时对话**，无需额外配置。三条访问路径中前两条均已确认可用。

**顺带确认的一个现象**：用同一个音频文件反复打多轮时，页面上会出现多条一模一样的候选人消息（ASR 结果相同）。**这是测试方式造成的，不是页面重复渲染** —— 真实面试每轮内容不同。README §4.2.1 已加说明，免得复现者误判。（用户本人就被这点疑惑过，所以特意写进文档。）

**同步官方仓**：**PR #13**（`xunzhekafei:dev-ai-contest-2026` → `open-vela:dev-ai-contest-2026`），3 commits / 5 files / +555 −1，`MERGEABLE`+`CLEAN` 可快进，CLA `pass`。

**PR #13 合并结果（9/14 14:30，`xunzhekafei` 合并）**：✅ 已并入官方仓 `dev-ai-contest-2026`，merge commit `3d29f69`。**又是 rebase-merge** —— 本地 `66333ff` 与官方 `3d29f69` 提交信息一致、SHA 不同（tree 相同，均为 `a621cc0`），按 §11.16 的老办法重新对齐并 `--force-with-lease` 推送，三方已一致。至此本队全部改动都在官方仓里，组员/评委按 README 4.0/4.1 从官方仓拉即可拿到最新代码。

### 11.18 收尾清理（2026-09-14）

两个 PR 都合并后，README §4.0 里那个 `<details>【过渡期，仅本队组员需要】官方仓尚未合并开发分支时的取码办法</details>` 已经**完全过时** —— 它自己的第一句就写着"组织者合并后本节即可忽略"，而官方仓现在就是最新的，照 4.1 拉即可。已删除（`README.md` −17 行 / +1 行），换成一行指向 4.2.1 展示页的提示。

**同时做了一遍仓库卫生扫描**：无未跟踪文件；无被跟踪的构建产物（`__pycache__` / `.pyc` / `.o` / `.img` / `.bin`）；无被跟踪的测试 WAV；`.gitignore` 覆盖到位且有注释说明。

### 11.19 静音门限 500 → 900（2026-09-14 晚；**9/18 晚已重烧，结论见 §11.22**）

**现象**：环境没变、代码也没变，但录音收不住尾 —— 明明环境很安静，每轮仍要录 10 秒以上才停。

**先排除掉的**：`git log` 显示 `audio_io.c` 最后一次改动就是 `7d9a0c9`（当晚排练用的那一版），之后只动过云端与文档；板级 `defconfig` 未覆盖任何录音参数；Kconfig 与 `app_config.h` 的编译期默认值都还是 9/13 定的那套（门限 500、增益 ×4、上限 30 秒）。**所以变的不是逻辑，是输入电平。**

**根因：判定阈值与现场底噪的余量本来就太薄。** 判停是拿每 100ms 一块的 RMS（**已经乘过 ×4 增益**）去比一个**绝对**门限：

| 场景 | 9/13 实测单块 RMS（×4 后） | 与门限 500 的余量 |
|------|--------------------------|------------------|
| 安静 | 最高 320（另一轮 381） | 仅 **1.3~1.5 倍** |
| 说话 | 556 ~ 1951，有效块多在 1000 以上 | 1.1~3.9 倍 |

而判停要求的是**连续**静音（20 块 = 2.0 秒，兜底 40 块 = 4.0 秒），**任何一块越过门限就把倒计时清零**。底噪只要往上抬一点（换摆位、开风扇/空调、供电源变化、手机离得近），安静段就会频繁越过 500 → 程序眼里"你一直在说话" → 2 秒和 4 秒都永远攒不够 → 只能等 30 秒硬上限或用户按 K2。

**处置**：门限上调到 **900**（现场判断，未逐值标定），源码默认值与文档同步更新：

| 文件 | 改动 |
|------|------|
| `app/ai_interview/app_config.h` | 默认值 500 → 900，并加注"这是底噪匹配值、换环境要重调" |
| `app/ai_interview/Kconfig` | 同上 |
| `README.md` | 参数表默认值、功能表「门限 500」→ 900，并把"门限 500 的来历"改写为 900 的来历 + 调法 |
| 本台账 §11.7 | 新增「启动前确认静音门限」，含 `set` + **自检方法** |

**构建已验证**（2026-09-14 晚）：按 §11.9 的命令重跑，**EXIT=0**，`nuttx/nuttx.bin` 重新生成（23:51），`audio_io.o` 于 23:50 重编 —— 证明改后的头文件确实被重新读取。并确认**全树没有第二处定义** `CONFIG_APP_AI_INTERVIEW_SILENCE_THRESHOLD`（`.config`、板级 `defconfig`、生成的 `nuttx/include/nuttx/config.h` 均无），所以源码里的 900 就是最终编进去的值。

> **⚠️ 9/18 晚补正：这条推论的落点要修正到 `app_config.h`，不是 Kconfig。**
> 这次重烧时查清了：**`nuttx/.config` 里根本没有 `ROLE` / `SILENCE_THRESHOLD` / `CLOUD_URL` 这几个符号**（该文件是 7/24 的陈旧文件，构建日志首行 `No configuration change.` 说明 `configure.sh` 没重写它），生成的 `config.h` 里自然也没有这些宏 —— 于是 `app_config.h` 里每个宏的 `#ifndef` **兜底值**才是真正编进去的值。
> **实际含义：改 Kconfig 的 `default` 是无效的，必须同时改 `app_config.h` 的兜底**（这次两处都改了，所以没问题；但你若只改 Kconfig 会静默不生效）。`app_config.h` 文件头的注释其实早就写明了这个机制。
> 反过来说，§11.19 上面那条"全树没有第二处定义"的核查是对的，只是没往下追问"那 Kconfig 的 default 到底起没起作用"。

> ~~想从二进制里反查这个常数是**行不通的**~~ —— **9/18 晚已找到可靠办法，此结论作废**：按**机器码**搜 `mov.w #900` 确实行不通（会撞上 `silk_encode_frame_FIX` 里 OPUS 的巧合），但按**功能锚点**搜是可靠的 —— 顺着 `getenv("SILENCE_THRESHOLD")` 那个字符串的地址找到加载它的 `ldr`，紧随的 `cbnz`（不跳 = 环境变量未设）落下来的那条 `mov.w r3, #900` 就是兜底值。定位细节见 §11.22。**不过权威判据仍然是板上那行日志**（见 §11.7 的自检）—— 静态反汇编只能"提前排雷"，不能替代运行时证据。

**⚠️ 尚未上板验证的两件事**（重烧前必须知道）：

1. **新默认值要重烧才生效**。没重烧的话，板上仍是 500，得靠 §11.7 里那条 `set SILENCE_THRESHOLD 900` 顶着。
2. **`set` 这条路本身也还没在真机正面验证过** —— 与 `CLOUD_URL` 那个悬案同源（内置应用是否继承 NSH 环境变量）。**自检办法已经写进 §11.7**：看 `[Audio] 开始录音（... 门限 RMS 900）` 这行打印的是 900 还是 500，一眼就能定性。这条日志本来就是为现场调参打的，顺带把环境变量继承这个悬案也一并验掉。

**下次上板要确认的**（按顺序）：

1. 启动日志那行门限数值 —— 确认环境变量是否真的生效（决定"必须重烧"还是"set 就行"）；
2. 安静 5 秒那一轮，看 `[Audio] N 秒, RMS 平均 ...` 里的**静音段数值与 900 的差距**；若安静段**最低≈最高≈平均**且都 >900，那就不是房间噪声而是直流偏置/恒定噪声，抬门限治标不治本，得去直流；
3. 正常答一轮，确认**说完 2 秒内收尾**，且**中途没被截断**（这是抬门限唯一的反作用：门限过高会把小声说话当静音，把回答砍断）。

> 判据留在日志里就够了，不必重烧试探：`[Audio] N 秒, RMS 平均 X [最低 Y, 最高 Z] (门限 T), 本秒人声 P%`。

### 11.20 面试官变「话痨」：模型在抄自己（2026-09-15 凌晨）

**现象**：`next_question` 的回复从正常的 100~200 字膨胀到 **400~570 字**，并带上一整套模板 ——`**判断：提出新问题**` / `理由：` / `新问题：` / `问题设计说明：（Markdown 表格）` / `下一步：`。TTS 会把它们**逐字念出来**，演示时非常难看。

**排查结论：不是提示词被改过，是模型在抄自己。**

| 证据 | 结论 |
|------|------|
| `git log --follow skills/next_question.json` | 自 7 月初始提交 `525d227` 起**一次都没改过**（694 字节，内容逐字未变）—— 不存在"之前的简洁版本"被覆盖 |
| 运行中 `/api/history` 的真实会话 | 模型的**前几条回复本身就是这种分析腔**，且**越写越长**：460 → 570 → 533 → 456 → 424 字 |
| `app.py:78` `session.add_ai_message(ai_text)` | 模型原始输出被**原样**存进 history，下一轮就成了自己的范例 → **自我强化** |
| 触发源 | 用同一段"喂喂，你好。"反复测试 → 模型面对"不配合的候选人"开始解释自己的判断（`建议：`/`理由：`），第一段分析腔就此进入 history |

**⚠️ 这个故障的重要性质：一次就污染整个会话，而且不会自己恢复。** 演示当天若中途出现一轮被带歪的回复，后面每一轮都会继续被带歪 —— 恢复手段只有**清会话/重启云端**重开一场（已写进 §11.7）。

**修复**：重写 `skills/next_question.json` 的 `system_prompt`，对齐 `generate_feedback` 在 9/14 加的「长度硬性要求」写法 —— 只输出对候选人说的话、禁 Markdown、**120 字以内**、禁评价与旁白、回答无效时不点评只再问一次，并给出正/误示例。

**验证（A/B，输入用的就是那条被污染的真实历史）**：

| 输入 | 旧提示词 | 新提示词 |
|------|---------|---------|
| 被污染历史 + 「面试官，你好。」 | **493 字**，含判断/理由/表格/下一步 | **82 字**，纯口语 |
| 干净历史 + 无效回答「喂喂，你好。」 | — | 27 字 |
| 干净历史 + 正常回答 | — | 50 字（**没被压瘦**） |

再走**生产路径**（`next_question()` 自己 `load_skill`）连跑 3 次：**79 / 59 / 72 字，零格式残留**（`**` / `---` / `|` / `判断：` / `理由：` 全无），`next_action` 均为 `continue`。

**顺带测过、结论是"不用改"**：`start_interview` 在空历史下本身就是 56~83 字；`generate_feedback` 9/14 已加 200 字上限；`evaluate_answer` / `check_timeout` 在真实链路上不可达。

**已清场**：云端已重启（新 PID 7443，`setsid` 脱离会话），`/api/history` 回到空态，key 自检通过。**板子那边不用动** —— 下次 K1 会拿到一个空会话。

> 复现脚本留在 `/tmp/ngq_ab.py`（未入库）。要重做单变量对照时改它即可；注意它会真打 LLM，需要 `MIMO_API_KEY`。

### 11.21 面试官「问的问题有出处」：题库 + 面试方法论 + 回复闸门（2026-09-18，**未上板**）

**要解决的三件事**（都不是"再加个功能"）：

1. 之前的问题是**模型现编**：问得不差，但换个岗位问的路子也差不多，问不到那个岗位真正会被问到的东西；
2. 没有面试官该有的**纪律**：会点评（"这个思路不错"）、会一次问两问、会揪着同一话题追到底；
3. 端侧默认岗位是 `产品经理` —— 一个**题库里根本没有**的岗位。

**变更一览**：

| # | 变更 | 位置 | 说明 |
|---|------|------|------|
| 1 | 题库落地：**2830 题**（AI 侧 6 个岗位） | `question_bank/`（新） | 与 `~/myagent/interview/data/` **逐字节一致**；带可复现导入脚本、字段表、出处说明、已知局限 |
| 2 | 选题模块 | `cloud/question_bank.py`（新） | 岗位归一化/别名 → 关键词检索 → 类别轮换（固定优先级）→ ≤400 字参考块；纯标准库、无随机、可复现 |
| 3 | 提示词 | `skills/next_question.json`、`skills/generate_feedback.json` | 加【面试纪律】+ 参考块占位符；报告改固定 6 句、必须引「」原话 |
| 4 | 回复闸门 | `cloud/reply_guard.py`（新） | **出口与入口**都剥掉「判断：/理由：/---」这类元叙述 |
| 5 | 岗位默认值 `产品经理` → `AI 应用开发` | Kconfig、app_config.h、app.py、README、api_protocol.md | 与题库对齐；NSH `set` 的空格陷阱已写进 4.7 |
| 6 | 校验工具（4 个） | `cloud/rehearsal.py`、`ab_next_question.py`、`test_question_bank.py`、`test_reply_guard.py` | 用法与判据见 `cloud/README.md` 5.5 |

**证据一：PC 端 11 轮全流程**（`cloud/rehearsal.py`，2026-09-18 06:18 复跑，岗位 `AI 应用开发`）

| 项 | 实测 | 判据 |
|----|------|------|
| 轮次 | 11 轮**全部 HTTP 200**，末轮 `next_action=finish` 出报告 | 全 200 + 末轮报告 ✅ |
| 历史 | 22 条 | 期望 22 条 ✅ |
| 问句长度 | 38~68 字（第 11 轮报告 139 字） | ≤150 / 报告 ≤250 ✅ |
| 单轮 TTS | 最大 **1335 KB**（报告轮）；全程合计 5.36 MiB | 端侧上限 8 MiB，单轮最坏仍留 6 倍余量 ✅ |
| 参考块泄漏 | `LEAK_STRINGS` 一个都没出现 | 0 泄漏 ✅ |

> **问句一眼能看出是题库来的**：混合召回怎么配合、语义缓存怎么判重、评测集怎么构建、金标集哪来的、向量与关键词召回怎么融合排序 —— 这些"岗位内行问题"是接题库之前不会出现的。

**证据二：单变量 A/B**（`cloud/ab_next_question.py --n 30`；P=提示词、B=题库开关、R=报告）

| 轮次 | 这一轮改了什么 | P 组（提示词） | B 组（题库） | R 组（报告） |
|------|---------------|---------------|-------------|-------------|
| 第 1 轮 | 初版：纪律 7 条 + 正/误示例 | ❌ 残留 **3/30**（被污染历史那几例，最大 229 字） | ⚠️ 长度 29.9→38.1 字（判据误报，见下） | ❌ 引用原话 **83%** |
| 第 2 轮 | 删掉提示词里的「错误示例」 | ❌ 残留 **4/30**（没好转；旧提示词那一臂也中了 1 次） | 未重测 | ✅ **90%**、0 残留、最长 188 字 |
| 第 3 轮 | 纪律 7→3 条 **+ 加 `reply_guard`** | ✅ **0 残留、0 兜底**、最长 66 字、100% 问号结尾、平均 39.7 字（旧版 42.1） | 未重测 | 未重测 |

**B 组那条"不达标"是判据写错了，不是回归**：`MAX_LENGTH_RATIO = 1.2` 是为 P 组写的（改提示词不许把话说长），套到 B 组就成了误报 —— 题库里的题本身比自由提问更具体，问到点子上必然多几个字；38 字仍远在提示词 120 字硬上限内。已把该判据限定为只对 P 组生效，B 组改判"最长问句 ≤120 字"（见 `ab_next_question.py` 判定段注释）。**这条改动是看完结果才做的，属于事后调整判据，故在此明说。**

**证据三：单元测试**（都不联网、不花钱）：`test_question_bank.py` **22 项**、`test_reply_guard.py` **22 项**，全过。

**关键结论：提示词只能"劝"，拦不住的要在代码里拦。**

把闸门 short-circuit 掉再量同一件事（`/tmp/diag_meta.py`，未入库）：**同一条被污染的历史 ×10 次，5 次仍然是元叙述**（169~237 字）。所以第 3 轮那个"0 残留"**不是模型学乖了**，是闸门把跑偏的逐条救了回来。救回来的真实样子（原始输出 211 字，过闸 58 字）：

```
原始：判断：追问细节 --- 理由：候选人的回答非常简短…我需要追问… --- 新问题：> 您提到…
      --- 下一步：等待候选人回复后，根据其回答深度决定…
过闸：您提到在企业服务公司做了五年产品经理，能具体说说您负责的是什么产品吗？
      在这个过程中，您主导过哪些比较有挑战性的项目？
```

**未验证 / 已知风险**：

1. ~~**全部未上板**（含 9/14 的门限 900）~~ —— **9/18 晚已重烧上板并跑了两场真机面试**，见 **§11.22**。其中**「题库确实注入」这一条没有直接日志证据**：注入是 `llm_service.py:165-169` 的**无条件调用**且不打印任何日志，只能靠两头推断（角色对得上 + `build_reference_block` 实测返回 239~245 字的 RAG/向量检索参考块）。想留证据就得给注入加一行日志；→ **已补上（2026-09-29，§11.25）**：现在每轮都打印 `[题库] 本轮注入参考块：N 字（轮次 …，检索词 … 字）`，11 轮排练里实测 12 行（含 1 轮静音自检那场的对照）。
2. **「模型抄自己」只是被兜住，没有根治**：长会话下模型仍可能跑偏，闸门保证的是"念出来的永远是个问题"，不是"模型永远不跑偏"。这也是 §11.20 那条演示级风险的现状；
3. **报告端没有闸门**：`strip_meta()` 会砍掉报告里的非问句段落，绝不能套用；报告若再出现 Markdown，目前只能靠提示词（第 2 轮实测 0 残留，但不保证下一版模型仍如此）；
4. **英文侧 1647 题只做了裁剪**，没有翻译、没有人工审校，只保证"裁在词边界上"；
5. **静默退化**：题库缺失或岗位名对不上时面试照跑、只是不再注入参考题 —— 演示前按 §11.7 第 4.5 步自检（一条命令）。

**演示日手册已同步**：§11.7 新增「第 4.5 步：确认题库已加载 + 岗位映射对得上」。

### 11.22 重烧上板 + 真机面试验证（2026-09-18 晚）

> 这一节是**本作品首次在真实面试（而非 PC 病态输入）下的全流程验证**，也是 §11.19 与 §11.21 两处「未上板」的收尾。

#### 重烧全流程

按 §11.9 的定论走，两步都无异常：

```bash
# ① 编译（不需要板子）
cd ~/vela-opensource && ./build.sh vendor/allwinnertech/boards/r528/r528s3-velaevb1/configs/nsh/ -e -Wno-error -j32
# ② lichee 环境里打包（pack 需要 lunch_nuttx 导出的环境变量）
cd vendor/allwinnertech/lichee && source vela_env.sh && source envsetup.sh \
  && lunch_nuttx r528s3-velaevb1 && m && pack
```

| 项 | 结果 |
|----|------|
| `build.sh` | **EXIT=0**，末尾 `Minimal configuration saved to 'defconfig.tmp'` 正常（§11.9 那个 `apps/examples/Kconfig` 陈旧项的坑没复发） |
| `pack` | `pack finish`，退出码 **0**，镜像刷新为 **`Sep 18 23:02`**（旧的是 `Sep 13 10:32`，即板上原来那版） |
| 产出 | `vendor/allwinnertech/lichee/out/r528s3/velaevb1_nand/rtos_nuttx_r528s3-velaevb1_uart0_256Mnand.img`（40,078,336 字节，与旧镜像同尺寸 —— 只改了两个常量） |
| 烧录 | PhoenixSuit（Windows 物理机）。⚠️ **本板串口接在物理机上，不在虚拟机里**，所以板子控制台的命令都要在物理机上敲 |

#### 静态验证：两个改动都在固件里

| 验证对象 | 方法 | 结果 |
|----------|------|------|
| 岗位默认值 | 直接在 `nuttx.bin` 里按字节搜 UTF-8 串 | `AI 应用开发` **×1**、`产品经理` **×0** |
| 静音门限 | 反汇编 + 功能锚点定位（见下） | 兜底常量 **900** |

**反汇编锚点法**（§11.19 那条"反查行不通"的替代方案）：

1. 对象文件是 **LTO 字节码**（`apps/.../audio_io.o` 只有 `.group` 段，`objdump -d` 输出为空）→ **必须反汇编链接后的 `nuttx/vela_nsh.elf`**；
2. `strings -t x` 拿到 `SILENCE_THRESHOLD` 的文件偏移，按所在段换算成 VMA（`.text` 的 `VMA = 0x41400000 + (off - 0x2000)`）；
3. 在反汇编里搜该 VMA → 找到字面量池条目，再找引用它的 `ldr`；
4. 得到的序列是：
   ```
   ldr  r0, [pc, #412]  @ 载入字符串 "SILENCE_THRESHOLD"
   bl   getenv
   cbnz r0, <环境变量分支>      @ 设了就走 atoi
   mov.w r3, #900               @ ← 兜底值
   ```
   紧邻的字面量是 `MAX_REC_SEC` / `PCM_DEV` / `MIC_GAIN` —— 正是 `app_config.h` 那四个可运行期覆盖的参数，**不是 OPUS 里的巧合匹配**。

> 注意这是"提前排雷"，**权威判据仍是板上日志**（§11.7）。

#### 真机面试结果（两场）

云端日志（Flask 侧）：**1 次 `/api/health` + 13 次 `/api/interview`，全部 HTTP 200**，来源 `172.20.10.5`（板子）。技能序列 **`next_question` ×11 + `generate_feedback` ×1**。

| 验证项 | 结果 |
|--------|------|
| **重烧生效** | ✅ 板上日志 `门限 RMS 900`（无需 `set` 顶着）；云端侧 `role=AI 应用开发`（旧固件是「产品经理」） |
| **报告功能** | ✅ **首次在真实 10 轮面试下端到端跑通**（此前 §11.13 只用 PC 病态输入验过路由与体积）。报告 141 字、TTS 1,313,324 字节，内容含对话细节（「递归转换树图为Markdown」「上下文压缩」）→ 确实读到了完整历史 |
| **话痨回归** | ✅ 无复发。各轮文本长度 `5 14 23 37 47 57 59 65 66 68 77 90 98 141`，面试轮次全在 98 字以内（话痨时是 400~570） |
| **8MB 上限** | ✅ 最大音频 1.3MB，余量约 6 倍 |
| **回复闸门** | ✅ 兜底 0 次（无一轮需要被替换成兜底问句） |
| **静音短路** | ✅ 真实链路里出现过一次并正常工作（「抱歉，我没听清，请再说一次。」） |

#### ⛔ 发现的演示流程坑（**未改代码，已写进 README**）

**报告只在第 11 次按 K1 时出现，且全链路没有任何关键词识别** —— 对板子说「结束面试」不会结束面试、也不会出报告，那句话只会被当成一轮普通回答（日志里该场走的是 `next_question`，面试官回一句告别语就继续等下一位）。

判据是 `cloud/llm_service.py` 的 `len(history) - 1 >= HISTORY_FINISH_THRESHOLD`（阈值 20 条消息 = 10 个问答对），**这是出报告的唯一路径**。

**团队决策：不动代码**（距截止 2 天，改动需重新验证，且关键词有误触发风险），改为**把逻辑在 README 里写清楚** —— 新增 `README.md` §4.5.3「一轮面试的完整逻辑（何时结束、报告从哪来）」，含链路、轮次表、判据出处、报告后的端侧行为（清空 `session_id`、回 IDLE、再按 K1 即全新一场）、异常路径表；§4.8 新增第 8 条交叉引用。

> **演示必须答满 10 轮。**

#### 一处曾误判的地方（方法论）

`generate_feedback` 的日志显示 `消息数=2`，一度被我判为"报告没看到面试历史"。**读代码后发现是设计如此**：它把整段对话拼成**一条** user 消息（`llm_service.py:263-266`），所以 2 = system + 那一条。**看日志里的计数前先读代码。**

#### 遗留

1. ~~**题库注入无直接日志证据**（见 §11.21 第 1 条）—— 只能两头推断。要留证据需给注入加一行日志。~~ **已解决（2026-09-29，§11.25）**：注入处已加日志，实测可观测。
2. **`set SILENCE_THRESHOLD 800` 这个悬案仍未正面验证** —— 本次只确认了"不设环境变量时板上是 900"，没有实测运行期覆盖是否生效。
3. 演示前仍需轮换 MIMO key（§11.5 第 9 条）。

### 11.23 PR #15 合并与分支对齐（2026-09-19）

**PR #15**（`xunzhekafei:dev-ai-contest-2026` → `open-vela:dev-ai-contest-2026`），标题「云端接入 2830 题离线题库 + 回复闸门；端侧默认岗位改「AI 应用开发」」，共 **6 个提交**：`59cc0bf` 题库+方法论 / `3ae1c33` 回复闸门 / `8432ab5` 端侧岗位+文档 / `46b67a1` 日志归集 / `5774286` README §4.5.3 / `ed93e9f` 台账 §11.22。开 PR 时只含前 3 个，其余 3 个于 9/18 晚推入同一分支（含 `logs/` 的那次推送，在**用户明确点名授权后**一次成功，见 §11.21 的推送结论）。

**合并结果（2026-09-19，用户合并）**：✅ 已并入官方仓 `dev-ai-contest-2026`，官方仓前进到 **`0140d66`**。**又是 rebase-merge** —— 6 个提交全部换新 SHA（官方侧为 `abb99d0`/`8109813`/`0c8f29c`/`df9f2d7`/`14139ff`/`0140d66`），与本机 SHA 不同，但 **tree 完全相同（同为 `6334db7`）、`git diff` 零差异**。判定与对齐按 §11.16 的老办法：

```bash
git branch -f backup/pre-realign-pr15 ed93e9f   # 先留退路
git stash push logs/                            # 保护正在增长的会话日志
git reset --hard upstream/dev-ai-contest-2026
git stash pop
git push --force-with-lease openvela dev-ai-contest-2026
```

推送结果 `ed93e9f...0140d66 (forced update)`，**三方已一致：本机 = fork = 官方 = `0140d66`**。

### 11.24 文档勘误：README §4.5.3 的多轮上下文描述（2026-09-19）

复核报告素材时发现 `README.md` §4.5.3 有一句**与代码不符**：

> ~~"板子每轮都带上 `session_id` 与对话历史，云端据此接上下文"~~

**代码事实**：端侧请求体里 `history` 恒为空数组（`app/ai_interview/network_client.c:362` 手拼 JSON，同文件 `:349` 有注释"history 恒为空数组：多轮上下文由云端按 session_id 维护"）。**多轮上下文完全由云端按 `session_id` 维护，端侧不保存任何对话历史。**

已改为按代码口径描述，并补充"会话与历史都只存在于云端进程内存中，重启云端即全部清空"。这处修订不影响功能，但 README 是**评委复现时的主要读物**，原表述会让人误以为端侧有历史缓存逻辑。

> 方法论：这类"文档比实现更乐观"的偏差在本项目里反复出现（R3 修过 4 处、§11.21 的"向量检索"措辞也是同类）。**写文档时以代码为唯一事实来源。**

### 11.25 赛后长期迭代第一批：会话落盘 / 语音结束 / 报告导出（2026-09-29，**纯云端，未上板**）

大赛 9/20 截止、提交材料（报告 + 视频 + 全新克隆复现验证）已完成后，项目转入**长期迭代**：不再为比赛赶工，而是做成一个能天天用的单人自练工具。这一批的四条硬约束：

| 约束 | 含义 |
|---|---|
| **只动云端** | `cloud/**`，一行 C 代码都不改，不重新烧录 |
| **向后兼容** | 板上固件保持不动，新云端必须能被**旧固件**正常调用 |
| **单人自练** | 不做多用户 / 账号 / 分享 |
| **局域网** | 不做鉴权 / TLS / 公网，`0.0.0.0:5000` 现状保留 |

向后兼容是硬约束，它决定了协议层能做什么：端侧 `network_client.c` 只解析 5 个字段（`session_id / next_action / text / user_text / tts_audio`），`next_action` 是 **16 字节定长**（`network_client.h:48`），端侧只在 `strcmp(next_action,"continue") != 0` 时清会话（`main.c:207`）。**所以响应体只能加字段、只能动值，"continue"/"finish" 两个值必须保持** —— 这一点本轮没有被违反。

#### 审计出的 7 个问题（逐条读过代码/跑过命令，不是猜的）

| # | 问题 | 性质 |
|---|---|---|
| 1 | **一次静音轮会把报告推迟到第 12 次 K1** | 空识别短路只 `add_ai_message`、没有对应 user 消息 → 历史变奇数。而判据是 `len(history) - 1 >= 20`，**一次静音就推迟一次**。文档却写死"第 11 次" |
| 2 | **`is_finished` 恒为 `False`** | `session_manager.finish()`（`:26`）零调用者 → "这场结束了没有"在云端根本不存在，网页无从渲染报告卡片 |
| 3 | **会话只活在内存** | Flask 一重启，上一场连同报告全没，也导不出 |
| 4 | 没有结构化评分 | 报告只有一段 200 字文本（团队锁定的上限），看不到分项 |
| 5 | 只能按到第 11 轮 | 想提前收尾没有别的办法 |
| 6 | `session_id` 直接来自请求体 | 一旦拿它当文件名就是路径穿越 |
| 7 | 三处"已存在但被绕过"的基础设施 | `clean_expired_sessions()` 用 `del`（`:41`）且零调用者；`rehearsal.py` 的 `LEAK_STRINGS`（`:55`）漏兜底标记 → **全链路失败也报绿** |

#### 做了什么

**P0（纯新增，零行为变化）**：`session_store.py`（原子写 + `save()` 永不抛异常）、`finish_guard.py`、`score_guard.py`、`report_export.py`，以及 6 个单元测试文件（**135 项全过**，纯标准库、不需要 key）、`run_tests.sh`（跳过真调 API 的 `test_services.py`）、`.github/workflows/cloud-tests.yml`。`.gitignore` 补 `cloud/data/` —— **刻意不放 `logs/`**：那是大赛要求提交的 AI 编码日志目录，运行期数据混进去是污染。

**P1（接线，用户可感知）**：

1. `is_finished` 变真：`next_action != "continue"` 时调 `session.finish()`，判据与响应体里的 `type` 完全一致；
2. 每轮落盘：位置在 **TTS 之后、`return` 之前**（不拖慢板子正在等的回包；`save()` 吞掉所有异常）；
3. `GET /api/export/<sid>?format=md|json`：`send_file` + `BytesIO` 免落临时文件；文件名**纯 ASCII**（中文标题写在正文里），避开 `Content-Disposition` 的 RFC 5987 编码坑；
4. 网页报告卡片 + 两个下载按钮。⚠️ 关键点：**轮询指纹必须加 `is_finished` 与评分状态**，否则报告出来时 `msgs.length` 没变 → 指纹不变 → 卡片永远不刷新；
5. 语音结束：`finish_guard` 接在 `llm_interview()` 的阈值判断处做 **OR**，不放进 `handle_interview`、也不放进 `next_question`。四道闸：归一化 → ≤20 字 → 无问号 → 剥掉首尾客套后命中白名单。**宁可漏判不可误判**：「没问题」「可以了」「就这样吧」「没了」故意不在白名单里 —— 它们在技术回答里都太正常；
6. **空识别奇偶性修复**：短路回复照常返回、照常有声、**只是不进历史**；
7. `normalize_role` 短键收紧 + 参考块注入加日志 + 短查询不注入参考块（`MIN_QUERY_CHARS = 4`）。

#### 实测证据（全部为本机真跑，不是推断）

```bash
bash run_tests.sh                       # 6 个测试文件全部通过（135 项，不需要 key）
python3 rehearsal.py --rounds 11        # 11 轮全 HTTP 200；第 11 轮 type=report / next=finish；
                                        # 历史 22 条（期望 22）；最长回复 183 字；TTS 合计 6.18 MiB；
                                        # 导出 md/json 均 200
python3 rehearsal.py --say-finish --rounds 3
                                        # 说「结束吧」→ ASR 转写 '结束吧。' → 判据命中 → 第 3 轮出报告
python3 rehearsal.py --no-tts           # 3 轮静音：每轮 14 字短回复 + 有音频；历史 0 条 ✅
```

* **重启存活**：跑完 11 轮 → `kill` 掉 Flask → 重新起 → `GET /api/history?session_id=…` 仍返回 `is_finished=True / question_count=11 / 22 条消息`；不带参数返回磁盘上最近一场；`/api/export` 仍能导出（HTTP 200，5124 字节）。
* **注入可观测**（补上 §11.21/§11.22 的遗留）：11 轮里 12 行 `[题库] 本轮注入参考块：N 字（轮次 …，检索词 … 字）`。
* **短查询守卫**：`build_reference_block("AI 应用开发", "嗯" / "好" / "然后呢")` 全部返回 **0 字**（此前会返回同样 3 道不相关的题），真实回答则返回 240 字。
* **`ab_next_question.py` 的假绿与崩栈**：`--group X` / `--group ""` 此前会"一组都不跑"却打印 ✅，现已拦下；`--n 0` 会除零崩栈，现已拦下；`load_skill` 加载失败时返回 `{}` → 取 `["system_prompt"]` 是 **KeyError 崩栈且崩在友好提示之前**，现改为提示"检查 `cloud/skills/` 是否拷过来了"。

#### 两条方法论（这一轮的主要收获）

1. **只查"不该出现"是不够的，还要查"是不是失败得体面"。** `rehearsal.py` 原先只查泄漏串，于是全链路失败时**依然是绿的**：模型调不通 → 各处 return 兜底串 → HTTP 200、结构完整、没有泄漏串，所有既有判据全部通过，脚本打印"✅ 排练通过"。这是最坏的一种假绿 —— 它让"上板前先排练一遍"这道防线形同虚设。现在专门查一类 `FALLBACK_STRINGS`（`生成报告失败` 等），**兜底文案出现即不合格**。
2. **判据要跟着判据本身变。** 报告轮现在由结束判据决定，"末轮必是报告"只在 `--rounds 11` 或 `--say-finish` 时成立；`--rounds 3` 下写死它会变成**假失败**。同理，`--no-tts` 原先只是"省一次 TTS 调用"，可它发的 44 字节静音 WAV 必然触达空识别短路，第 1 轮就自己 break —— 这个开关**从没成功跑完过一轮**。现在它是静音自检，而且是问题 1 那条修复的直接回归测试（3 轮静音后历史必须是 0 条）。

#### 勘误与替代

**§11.24 那句"会话与历史都只存在于云端进程内存中，重启云端即全部清空"自本日起不再成立** —— 会话每轮落盘到 `cloud/data/sessions/`，重启后网页与导出仍可读。§11.24 记录的当时状态没错，但别再引用那句话描述现状。

#### 遗留（下一批）

* **P2 结构化评分**（独立一次 LLM 调用 + 后台线程，必须在 TTS 之后发起）：`score_guard.py` 已就绪但**尚未接线**；`skills/score_report.json` 未建；`POST /api/score/<sid>` 未做。整块可独立砍掉，不影响 P1。
* **P3 可选**：无头截图存档（本机 node 有、**chromium 没有**，已确认不可用）、严格证据校验。
* **端侧 4 项**（本轮绝不碰，等下次重烧一并处理）：K2 在非 ERROR 态会卡死录音（**真 bug，优先级最高**）、LED 快慢闪完全一样、K3 未实现、README 里 K2 描述与实际不符。
* **板级验证**：旧固件 + 新云端跑通 11 轮 —— 这是唯一能正面证明"向后兼容"的方式，本轮只做到了 PC 端全链路。

---

### 11.26 端侧两处修复：K2 卡死录音 / LED 快慢闪（2026-09-30，**未上板**）

接 §11.25 遗留里的端侧 4 项，本轮处理前两项。两处都只改端侧 C，**协议与云端零变化**。

#### 一、K2 在待机态会把机器推进假录音态（真 bug，§11.25 标的"优先级最高"）

**机理**（`app/ai_interview/main.c` 的 `check_buttons()`）：

```c
if (s2 == 0 && g_key2_last == 1) {
    g_abort = 1;
    if (!busy) {                                  /* ← 错在这里 */
        state_machine_post_event(EVENT_BUTTON_PRESS);
    }
}
```

原注释写的是「不忙碌时**说明停在 ERROR 态**」—— 但 `!busy` 在 **IDLE 同样成立**：

```
IDLE 按 K2 → !busy 成立 → 投 EVENT_BUTTON_PRESS
           → 状态机 IDLE --BUTTON_PRESS--> RECORDING
           → 工作线程压根没收到 CMD_START
           → 停在"录音中"：LED1 快闪、其实什么都没录
```

**没有任何超时能把它救出来**：`EVENT_RECORD_TIMEOUT` 在状态机里有处理分支，但全仓**没有一个投递点**（录音的时长上限在 `audio_record_wav()` 内部处理，走的是"正常结束"那条路，不会经过这个事件）。只能再按一次 K1 把它带回正轨 —— 那已经不是"取消"，是把机器弄糊涂了。

**修法**：不再从 `busy` 反推，**直接问状态机**（`state_machine_get_current_state()`）：

| 情形 | 行为 |
|---|---|
| `busy`（录音／上传／播放中） | 置 `g_abort`，取消当前一轮 |
| 状态机在 `STATE_ERROR` | 投 `EVENT_BUTTON_PRESS` → 回 IDLE |
| 其他（IDLE） | **什么都不做**；顺带**不再置 `g_abort`** —— 在待机置它没有意义，只会让下一个真正开始的轮次在起跑线上被中止 |

#### 二、LED 快慢闪完全一样

`state_machine_update_led()` 里 RECORDING 与 UPLOADING 两个分支写的是**同一段代码**：每次调用翻转一次。而主循环固定 100ms 调一次 —— 所以两者都是每 100ms 翻一次，注释里写的 200ms／800ms **从没实现过**。

**修法**：把节拍显式写成 tick 数（1 tick ≈ 100ms，由主循环给定）：

| 状态 | 图案 |
|---|---|
| IDLE | 常亮 |
| RECORDING | `##..` —— 亮 200ms／灭 200ms |
| UPLOADING | `########........` —— 亮 800ms／灭 800ms |
| ERROR | `#.#.#.......` —— 三短闪（亮 100ms ×3）后停 600ms，1.2s 一个循环 |

顺带：**换状态时把 tick 归零**，图案从头开始 —— 否则"三短闪"可能从某个相位中途接上，看起来只有两下。

#### 验证状态

* ✅ **PC 端语法检查**：`gcc -fsyntax-only -Wall -Wextra`（`nuttx/ioexpander/gpio.h` 与 `sys/ioctl.h` 用桩头文件替代），`main.c`、`state_machine.c` 均无警告。
* ✅ **图案验算**：把 `blink_square()` 与错误图案的表达式单独跑了一遍，输出与上表一致；快:慢 = **4 倍**，人眼可分辨。
* ✅ **已上板验证（2026-09-30）**：重烧后逐条实测通过。串口原文（节选，本机实测）：

  ```
  [Main] K2 按下 —— 当前待机，无操作          ← 待机按两次，**后面没有** IDLE-->RECORDING
  [Main] K2 按下 —— 当前待机，无操作
  [Main] K1 按下 —— 开始面试
  [StateMachine] IDLE --[BUTTON_PRESS]--> RECORDING

  [Main] K2 按下 —— 取消当前一轮              ← 录音中按：真的取消了
  [Audio] 录音结束: 已取消

  [LED] 错误状态 - LED1 三短闪
  [Main] K2 按下 —— 从错误态返回待机          ← 错误态按：回 IDLE
  [StateMachine] ERROR --[BUTTON_PRESS]--> ...
  ```

  **判据（最关键的一条）**：那两行"当前待机，无操作"之后**没有出现** `[StateMachine] IDLE --[BUTTON_PRESS]--> RECORDING` —— 这正是修复前必然会出现的假录音迁移。LED 快慢闪由人眼确认可分辨（串口里那两行 `[LED] 录音中/上传中` 是状态迁移时打的，不随节拍刷新，所以频率只能目视）。

#### 勘误：K2 在上传阶段仍取消不了（本轮发现 → **已于 §11.29 修复**）

实测里露出来的一条**既有行为**（非本次引入）：

```
[Main] K2 按下 —— 取消当前一轮      ← 上传重试期间按的
[Cloud] 上传失败: ...（第 3/3 次）   ← 但它还是走完了三次重试才进 ERROR
```

上传是 libcurl 的阻塞调用，不像 `audio_record_wav()` / `audio_play_wav()` 那样带 `g_abort` 检查，所以**上传期间按 K2 只是置了标志、并不会中断本轮**。本轮只改了日志措辞（"取消" → "取消当前一轮"），让这个落差显得更明显了一点。

→ **已修（2026-09-30，见 §11.29）**：重试循环加 `g_abort` 检查、取消先于失败判定、`STATE_UPLOADING` 补 `EVENT_ERROR → IDLE`。方案比当时估计的"加一句检查"多两处 —— 漏掉任何一处这条路都走不通。

#### 遗留（仍未动的端侧项）

* **K3 未实现**（按了只打日志）—— 不是 bug，是没做的功能。
* README 里 K2 的描述本轮已同步（见 README §4.5.2 那张表下的注）。
* **旧固件 + 新云端的上板验证**（§11.25 遗留）仍未做 —— 它是证明"向后兼容"的唯一方式。

---

### 11.27 新工作模式第一次真机跑通 + VMware 端口转发的静默抢占（2026-09-30）

#### 背景

赛后定的新分工是「Windows 上写代码 → VM 只负责编译固件 → 烧录在 Windows」，并且**云端 Flask 改跑 Windows 原生**（不再跑在虚拟机里，也就不再需要 VMware NAT 端口转发）。本轮把它第一次跑通，途中踩到一个**只在新模式下才会出现**的坑。

#### 现象

板子与 Windows 都连上了同一个手机热点、`app.py` 已在 Windows 上运行，板子仍报：

```
[Cloud] 健康检查失败: Couldn't connect to server
[Cloud] 上传失败: Couldn't connect to server        （三轮全失败）
```

#### 排查（每一步都用工具定位，没有猜）

| 步 | 命令 | 结果 |
|---|---|---|
| 1 | `ipconfig`（Windows） | 拿到了 `172.20.10.2` —— **正是固件里编死的地址，地址没错** |
| 2 | `netstat -ano \| findstr :5000` | ⚠️ **有两个 TCP 监听者**（PID 6640、36320），正常不该有 |
| 3 | `Get-CimInstance Win32_Process -Filter 'ProcessId=6640'` | **`vmnat.exe`** —— VMware 的 NAT 服务 |
| 4 | `grep -A3 incomingtcp C:\ProgramData\VMware\vmnetnat.conf` | `5000 = 192.168.93.141:5000` —— 比赛期配的那条端口转发 |

#### 根因

那条转发规则是**持久配置**。§11.7 当时写的是"VMware NAT 端口转发是持久配置，不用重配"—— 它确实持久，**持久到虚拟机都关机了它还占着 5000 端口**：

```
板子 → 172.20.10.2:5000 ──被 vmnat.exe 接走──→ 转发给 192.168.93.141:5000（虚拟机，已关机）
                                                     ↓
                                                连接失败
```

新起的 Flask 虽然也绑在 `0.0.0.0:5000`（Werkzeug 开了 `SO_REUSEADDR`，Windows 下允许重复绑定），却拿不到连接。

**症状特征**：服务端一切正常（进程在、端口在监听、日志无异常），板子说连不上；失败是**连接级**的（curl 返回 `HTTP 000`，不是 404/500）。这表现和"防火墙拦截"很像 —— 但按 §11.8 的教训，**先查是不是有东西抢了端口，别先怀疑防火墙**。

#### 修法

VMware → 编辑 → 虚拟网络编辑器 → 更改设置（需管理员）→ VMnet8 → NAT 设置 → 端口转发 → 删掉 `5000` 那条。

只删**入站转发**，VMnet8 的 NAT 出站不受影响（虚拟机照样能上网）。**不要**直接手改 `vmnetnat.conf` —— 改了不会立刻生效，还得重启 `vmnat` 服务。

#### 顺带：Flask 起了两份

排查时看到两个 `python.exe app.py`（PID 36320 / 36500）。Werkzeug 默认开 `SO_REUSEADDR`，第二个进程也能绑上同一端口，请求落到哪个不确定。**清掉端口冲突后要确认只剩一份**：

```powershell
netstat -ano | findstr ":5000" | findstr LISTENING   # 应只剩一个 python 的 PID
```

#### 结果：整轮面试真机跑通

删掉转发规则、只留一份 Flask 之后，按 K1 说话 → 音频上传 → 面试官语音正常播回。这一轮同时验证了三件事：

1. §11.26 那两处端侧修复在真机上有效（测试 1~4 全过，见该节）；
2. **新固件 + 新云端**没问题 —— 端侧改动没有碰坏主链路；
3. **新工作模式成立**：Flask 跑 Windows 原生、板子直连 `172.20.10.2:5000`，**不需要任何端口转发**。这比老拓扑还少一跳。

#### 遗留

* `set CLOUD_URL` 的运行期覆盖**仍未正面验证**（§11.22 遗留 2、README §4.6）—— 本轮走的是编译期默认值，没有碰它。
* K2 在上传阶段取消不了（见 §11.26 末尾的勘误）。
* **旧固件 + 新云端**的向后兼容验证仍未做（§11.25 遗留）—— 本轮验的是"新固件 + 新云端"。

#### 同一轮里顺带验到 / 发现的

**① `finish_guard` 首次在真机上生效** ✅

实测那一轮候选人只说了三句，第三句被 ASR 转写为 `结束面试。`，归一化后命中白名单 → **第 3 轮就出了报告**（正常要第 11 轮）。会话落盘文件里可以直接看到证据：`question_count: 3`、`is_finished: True`、`messages: 6 条`。

顺带也验证了 **会话落盘在真实链路上生效**（`cloud/data/sessions/<sid>.json` 由板子那一轮真实写出）—— 在此之前它只在 PC 端被测过。

**② 报告缺了「」原话引用 —— §11.21-3「报告端没有闸门」第一次实机命中** ⚠️

`skills/generate_feedback.json` 里写着「必须至少引用一处候选人的原话……**这一条没有例外**」，但实测那份报告（80 字、四个维度全写"未涉及"）**没有任何「」引用**。

值得注意的不是"模型偶尔不听话"，而是**它暴露了排练覆盖不到的一类输入**：这一轮候选人三句分别是 **6 / 2 / 5 字**，而 `rehearsal.py` 的 11 轮用的是正常长度的回答（台账 §11.21 记的"报告轮 100% 含「」引用"就是那样测出来的）。**极短回答下这条要求会失效。**

**未修**。修法有两种，属于设计选择、需要先定：

1. **代码兜底**（同 `reply_guard` 的路子）：报告返回前检测有无「」，缺了就重试一次或补一句引用 —— 代价是多一次 LLM 调用；
2. **提示词补一句**覆盖退化情形（"若各维度均未涉及，也要引用候选人最后的发言"）—— 便宜，但按 §11.21 的教训，**提示词是"劝"、拦不住**。

要真做，建议同时给 `rehearsal.py` 补一组**极短回答**的用例，否则改完还是测不到。

---

### 11.28 `set CLOUD_URL` 运行期覆盖：真机正面验证通过（2026-09-30，**悬案关闭**）

#### 挂了多久

从 §11.22（9/18 晚）起就是遗留项，README §4.6 一直写着"代码路径已通，但**本队未在真机上正面验证过这条路**"。悬案的说法是：`app_config.h` 的 `app_cloud_base_url()` 先读 `getenv("CLOUD_URL")`，而内置应用是否真的继承 NSH 的环境变量，只在源码层面推过（`nuttx/sched/task/task_spawn.c:226` 会退化成 `environ`），没实测。

#### 第一次尝试：看那行打印（失败）

最直接的判据本该是启动时那行 `[Cloud] 云端接口: …`（`cloud_init()` 里 `printf`，无条件执行）。**但连续两次运行都没打印出来**：

```
[Main] 系统就绪，等待按键开始面试...
[Main] 云端健康检查...              ← 同一线程的下一行都出来了
[Main] K1: 开始面试                    （`[Cloud] 云端接口:` 却没有）
```

两次是同一线程按顺序打印、后一句出现而前一句消失 ⇒ **只能是被吞了**，不是没执行。根因是台账早记过的那条：**NuttX 的 stdio 非线程安全**，主线程正在刷 K1/K2/K3 三行帮助信息，与工作线程的输出互相踩掉（§11.7 记过"感知到的并发错行"是同一个根因）。

> 讽刺的是：**唯一能说明"当前用哪个地址"的那一行，恰恰是最容易被吃掉的**。

#### 第二次尝试：阴性对照（成功）

换一个**不依赖任何打印**的判据 —— 把 `CLOUD_URL` 指到一个**板子当时够不到**的地址：

| 步 | 操作 | 结果 |
|---|---|---|
| 1 | 板子连热点，`ifconfig` 确认 `wlan0 inet addr:172.20.10.5` | 在热点网段 |
| 2 | `nsh> set CLOUD_URL http://192.168.1.11:5000` | 这个地址**在热点网段上够不到** |
| 3 | `nsh> ai_interview` | **健康检查失败**：`[Cloud] 健康检查 HTTP 0 -> 云端不可达` |

**为什么这能证明覆盖生效**：编译期默认地址 `172.20.10.2` 在热点拓扑下**是通的**（当天早些时候刚跑通过整轮面试，见 §11.27）。所以：

* 若覆盖**无效**（走了默认）→ 健康检查应当**成功**；
* 实测**失败** ⇒ 它确实去连了 `192.168.1.11` ⇒ **覆盖生效**。

这个方法的价值在于：结论只看"连接成不成功"这个板上行为，**串口丢行、两个线程抢 printf 都影响不了它**。

#### 顺带一条失败记录（不影响结论）

验证过程中先试过让板子连家用 Wi-Fi（`CMCC-RGDx`），关联失败：

```
RTL871X: rtw_select_and_join_from_scanned_queue: return _FAIL(candidate == NULL)
RTL871X: indicate_wx_custom_event No Assoc Network After Scan Done
```

`candidate == NULL` = 扫完之后结果里没有这个 SSID，`renew` 拿不到 IP 是必然。最可能是**那是 5GHz 的 SSID 而板载 Realtek 只支持 2.4GHz**（中国移动路由器常把两频段分成两个名字），其次是被隐藏、或信号太弱。**本条与上面的结论无关** —— 阴性对照法不需要那个网络。下一条诊断命令是 `wapi scan wlan0`。

#### 遗留

* ~~**让那行 `[Cloud] 云端接口:` 变可靠**~~ —— **已做，见 §11.29**：挪到主线程、启动工作线程之前打印，并顺带报出来源。

---

### 11.29 端侧第二批：K2 上传取消防 + 云端地址打印挪到主线程（2026-09-30，**待重烧验证**）

接 §11.26 末尾的勘误与 §11.28 的遗留 —— 两条都很轻，合成一次重烧。

#### 一、K2 在上传期间取消不了（§11.26 实测发现）

上传是 libcurl 的**阻塞调用**、中断不了；但"重试之间的等待"本来是可以中断的，而原代码在整段上传流程里**完全不看 `g_abort`**。结果是：按下 K2 只置了个标志，板子照样走完三次重试才进错误态 —— 日志嘴上说"取消当前一轮"，实际要再按一次 K2 才能回待机。

修法三处，**缺一不可**：

| # | 位置 | 改动 |
|---|---|---|
| 1 | `main.c` 上传重试循环 | 每轮开始前看 `g_abort`；把 `sleep(3)` 拆成 30 个 100ms 小片、每片都看（与录音/播放的取消粒度一致） |
| 2 | `main.c` 失败判定之前 | **取消要先于失败判定**：置了 `g_abort` 就发 `EVENT_ERROR`（回 IDLE），而不是 `EVENT_UPLOAD_FAIL`（进错误态）。顺序反了会把一次用户取消记成一次故障，还会弹出"云端多半缺 key"这种自相矛盾的提示 |
| 3 | `state_machine.c` | `STATE_UPLOADING` 增加 `EVENT_ERROR → STATE_IDLE`。**少了这一条，前两条都白搭** —— 从 UPLOADING 发 `EVENT_ERROR` 会被静默忽略、状态机卡在上传态。这也解释了原来那条路为什么走不通 |

#### 二、云端地址打印挪到主线程（§11.28 遗留）

原来那行 `[Cloud] 云端接口: …` 由**工作线程**的 `cloud_init()` 打印，而启动那几秒主线程正在刷 K1/K2/K3 帮助信息 —— NuttX 的 stdio 非线程安全，实测被吞过两次。而它恰恰是排查"到底用了哪个地址"的**唯一直接信息来源**。

修法：从 `cloud_init()` 移除，改由**主线程**在 `pthread_create` **之前**打印（此刻只有它一个在写 stdout），并顺带报出来源：

```
[Cloud] 云端地址: http://172.20.10.2:5000
[Cloud] 来源: 编译期默认值（CLOUD_URL 未设或不合法）      ← 或者「环境变量 CLOUD_URL（运行期覆盖生效）」
```

**这一行以后就是 §11.28 那个问题的直接答案**，不必再绕道阴性对照法。

#### 验证（PC 端，这次做到了"能自动判"）

`state_machine.c` 里所有 GPIO 操作都以 `fd >= 0` 为前提，PC 上 `/dev/gpioN` 打不开 → fd = -1 → 写 LED 全部静默跳过。**于是迁移逻辑可以脱离硬件跑**，只要给 `ioctl` 一个空实现。

跑了 14 条断言（正常一轮 / 上传取消 / 录音取消 / 错误态返回 / 连续三次失败回 IDLE），**全部通过**。

**并且做了对照组**：拿修复**前**的 `state_machine.c` 跑同一套断言，那条 `UPLOADING --ERROR--> IDLE` **如期失败**（实际停在 UPLOADING），其余 13 条照常通过 —— 证明这个判据真能分辨"修没修"，而不是"看着绿"。

> 对照组这一步是刻意加的：§11.25 记过 `rehearsal.py` 的假绿教训 —— **判据必须能区分"没做"与"做对了"**，否则它只是装饰。

#### 上板验证（2026-09-30）

重烧后两条都实测通过。串口原文（断网状态下按 K1 说话，在**第 2 次重试之后**按 K2）：

```
[Cloud] 云端地址: http://172.20.10.2:5000                    ← ① 出现在「系统就绪」之前
[Cloud] 来源: 编译期默认值（CLOUD_URL 未设或不合法）             主线程打的，没有被吞
[Main] 系统就绪，等待按键开始面试...
...
[Main] 上传失败: ...（第 2/3 次）
[Main] K2 按下 —— 取消当前一轮
[Main] 本轮已被 K2 取消（上传阶段）                          ← ② 立刻生效
[StateMachine] UPLOADING --[ERROR]--> IDLE                  ← 直接回待机
[Main] K2 按下 —— 当前待机，无操作                             （§11.26 那条修复也还在）
```

**判据**：② 之后**没有**出现第 3 次重试，按键次数从两次降到一次。

#### 仍未验证

* `set CLOUD_URL` 之后「来源」那行应显示"环境变量 CLOUD_URL（运行期覆盖生效）" —— 这次跑的是编译期默认值那条分支。**覆盖本身**已于 §11.28 用阴性对照法验证过，这里只是没再看一眼措辞。
* 上传**当前那次**尝试仍然中断不了（libcurl 阻塞调用）—— K2 是在"重试之间"生效的。这是设计限制，不是缺陷。

---

### 11.30 报告端第一道闸：把「必须引用原话」从"劝"变成"拦"（2026-09-30）

#### 起因

§11.27 那次真机跑通里发现：`skills/generate_feedback.json` 明明写着「必须至少引用一处候选人的原话……**这一条没有例外**」，而实测那份报告（80 字）**一个「」引用都没有**。同时暴露了排练覆盖不到的一类输入 —— 候选人三句只有 6 / 2 / 5 个字。

#### 根因：提示词自相矛盾，模型自己找了个解释

把两条要求放在一起看就清楚了：

* 「评价必须落到他实际说过的话上，其中至少一处要引用他的原话」
* 「对话里没有涉及的维度，直接写「未涉及」」

四个维度**全**「未涉及」时，第一条没有任何可落地的位置 —— 模型于是把引用一起丢了。**这不是模型不听话，是要求本身在退化输入下打架。**

这也解释了为什么排练测不出来：`rehearsal.py` 的 11 轮用的都是正常长度的回答，四个维度总有可评的。

#### 修法：两条腿，缺一不可

| 层 | 做什么 | 文件 |
|---|---|---|
| **提示词** | 补一句专门覆盖退化情形：「即使候选人几乎没说话、四个维度全写「未涉及」，也照样要引用他仅有的那几句话里的一句」—— 把矛盾**解开** | `skills/generate_feedback.json` |
| **代码** | 首轮出来先查有没有「」引用；没有就补一次纠偏重试（原回复 + `RETRY_HINT` 一起发回去）。**只在缺的时候才多花一次调用** | `report_guard.py` + `llm_service.generate_feedback` |

同 §11.21 的结论：**提示词是"劝"，拦不住的要在代码里拦**。这次两者都要 —— 提示词负责把矛盾解开（提高一次通过率），代码负责兜住剩下的。

**两个判据分得很清**（这是本模块的设计要点）：

* `has_quote()` **硬判据**，决定要不要重试；
* `check_quote_evidence()` **软判据**，查引用是不是真出自候选人 —— **只记日志、不拦**。因为提示词明确允许"摘不出完整句子就摘关键词连起来"，那是合法的**拼接**而非连续原文，拿它当拦截判据会大面积误报（同 `score_guard.evidence_supported` 的取舍）。

**重试仍不合格**：**照发原文**，只记日志。宁可用一份缺引用的报告，也不为凑格式把好内容丢掉或机械拼一句引用 —— 报告本身是好的，缺的只是格式。

#### 验证（PC 端，不花钱）

* `test_report_guard.py` —— 18 项，纯标准库。样本逐字用真机那份缺引用的报告（`REAL_NO_QUOTE`）。
* `test_report_retry.py` —— 7 项，把 `call_llm` **打桩**，验接线：缺引用会重试、已引用不重试（零成本那条）、重试仍失败照发原文、重试消息里确实带了 `RETRY_HINT`、提示词里那条退化说明还在（删掉它问题会回来，所以专门断言它存在）。
* `run_tests.sh` 分档同步：`test_report_retry.py` 需要 `openai`，归"装依赖才跑"那一档（没装时**大声跳过**）。全量 9 个文件全过。

**对照组**（照 §11.25 那条方法论）：把 `llm_service` 里的闸门条件临时改成 `if False`，同一条测试立刻失败（`1 != 2`：没重试），还原后恢复通过 —— 证明判据真能分辨"接没接上"，不是"看着绿"。

#### 真机验证（2026-09-30，花了一次钱）

`rehearsal.py` 补了 `--short-answers`（三句极短回答：你好。/ 嗯。/ 还好吧。）与一条**此前根本不存在的判据** —— *报告轮必须含「」引用*。**后者才是关键**：排练原先只查报告**长度**、不查引用，所以 §11.27 那次失败是从这道防线里直接漏过去的（"测不到的路径等于没有这道防线"）。

```
rehearsal.py --short-answers --say-finish --rounds 3
```

**结果：通过。** 3 轮全 HTTP 200、第 3 轮 `type=report`、ASR 把「结束吧」转写成 `'结束吧。'` 并命中白名单、历史 6 条、导出 md/json 均 200、无兜底文案与泄漏串、报告 93 字。落盘那场会话里的报告原文：

> 候选人整体表现不佳，未展示出基本的技术能力。技术正确性无法判断。对技术深度与原理的理解未涉及。工程与场景思考未涉及。表达与沟通能力较弱，「结束吧」。建议候选人明确职业方向并做好充分准备。

再用闸门自己核了一遍：`has_quote` → **True**；摘出的引用是 `结束吧`，而候选人的原话（ASR 转写）正是 `'你好。' / '嗯。' / '结束吧。'` —— **软判据也全部对得上**，不是编的。

**结论**：退化输入（候选人总共只说了 3 + 2 + 3 个字）下，报告仍然带上了**真实**的引用。修法有效。

**兜底重试有没有被触发？—— 没有**（补查服务端日志）：报告那一轮只有**一次** LLM 请求（`LLM 请求: model=mimo-v2.5, 消息数=2`，即 system + user），紧接着就 `LLM 返回: …「结束吧」…`。若触发过重试，日志里会多一次请求、且 `消息数=4`（多一条原回复 + 一条纠偏指令）。

**所以这一次是「提示词那一半自己就够了」** —— 把那个自相矛盾解开之后，模型一次就按要求引用了。代码那道闸这次没派上用场，但它仍然该在：提示词是"劝"，§11.21 的教训正是**不能假设下一次它还听话**。

> **当天下午的第二次实跑正好给出了反面样本**：同一套代码跑「旧固件 + 新云端」时，首轮报告**没有**「」引用，是闸门重试一次才拿到的（日志见 §11.31）。
>
> **两次对照下来，§11.21 那句「提示词是劝，拦不住的要在代码里拦」算是拿到了正面证据 —— 如果只做提示词那一半，第二次就会漏出去。**

> 顺带（与本轮无关，同日发生）：**MIMO_API_KEY 已于 2026-09-30 轮换**。起因是一次误把 key 贴进 AI 对话（它同时进了会话记录与 PowerShell 命令历史）。§11.5 第 9 条那条"演示前再轮换一次"的待办至此彻底关闭。

#### 其余仍未做

* 报告端仍然**没有** `reply_guard` 那样的"剥"：`strip_meta()` 会砍掉报告里的非问句段落，绝不能套用（§11.21-3）。本次补的是另一件事（有没有引用），不是元叙述。

---

### 11.31 「旧固件 + 新云端」板级验证通过（2026-09-30）—— 最后一条板级遗留关闭

#### 为什么要单独验这一条

赛后那批云端迭代（会话落盘 / 报告导出 / 语音结束 / 报告闸）**没有动端侧一行代码**，协议层只加字段、`continue` / `finish` 两个值没变 —— 这是设计上的承诺，但"承诺"不等于"验过"。**旧固件不知道这些新东西存在**，是唯一能当对照组的角色（§11.25 遗留）。

#### 怎么做

固件用 **`39452b7`**（比赛截止那一版）编 —— 它的端侧代码与今天**完全相同**（除 K2 / LED / URL 打印那三处修改），但完全不含新云端的概念。烧录前先在镜像上直接 grep，确认传过来的确实是旧固件：

| 检查 | 结果 |
|---|---|
| 新代码独有的串（`当前待机` / `本轮已被 K2 取消` / `云端地址`） | 0 / 0 / 0 |
| 旧代码独有的串（`云端接口`） | 1 |
| **对照组**（`面试官`，新旧都有） | 3 —— 证明 grep 方法在这个 39MB 的 img 上有效 |

> 对照组不能省：没有它，"三个 0"也可能只是方法用错了 —— 而"因为方法错而绿"是本项目反复吃过亏的那类假绿。

#### 结果：通过，而且顺带把 §11.30 的兜底闸门也验了

服务端日志（板子地址 `172.20.10.5`，两次 `/api/interview` 均 HTTP 200）：

```
[结束] 候选人请求结束面试（命中 '结束面试'，实际轮次 1），提前生成报告   ← 新功能，旧固件毫不知情
[报告] 首轮没有「」引用，补一次纠偏重试                                  ← ★ 闸门触发
LLM 请求: model=mimo-v2.5, 消息数=4                                     ← 第二次调用（原回复 + 纠偏指令）
[报告] 重试后拿到了「」引用                                              ← 闸门兜住了
```

三条结论：

1. **旧固件 + 新云端成立**：板子（旧固件）说「结束面试」→ 新云端 `finish_guard` 命中 → 当场出报告并播回。旧固件只按 `next_action` 行事，对这机制一无所知。
2. **★ 兜底闸门这次真的派上了用场**：首轮报告没有「」引用，是代码那道闸重试一次才拿到的 —— 与 §11.30 上午那次（一次就过、闸门没触发）形成对照，构成"只做提示词会漏"的正面证据。
3. 题库注入日志也在：`[题库] 本轮注入参考块：273 字（轮次 0，检索词 7 字）`。

#### 本条**没有**覆盖的

* 走的是「说结束语 → 报告」那条路（2 轮），**没走满 11 轮的阈值路径**。后者的云端逻辑本次未改，且 PC 端排练默认就是 11 轮，已覆盖。
* 旧固件是**带病**状态（K2 那个 bug 在 `39452b7` 里没修，待机按 K2 会假录音）—— 预期的。**验完需烧回新固件。**

---

### 11.32 P2 结构化评分接线（2026-09-30，**纯云端，未上板**）

#### 做了什么

`score_guard.py` 早在 §11.25 那批就写好、测过了（32 项），但一直没接线 —— 这一轮把它接上：

| 件 | 内容 |
|---|---|
| `skills/score_report.json` | 新增。评分提示词，**不写死维度**，带 `{dimensions}` 占位符由代码注入 |
| `llm_service.score_interview()` | 新增。调 LLM → `extract_json` → `normalize` → 返回评分；任何失败返回 `{}` |
| `llm_service._dimensions_block()` | 把 `DIMENSIONS` 拼成提示词里的维度清单 |
| `app._start_scoring()` | 新增。报告轮之后**起一个后台线程**评分，写进会话 + 落盘。返回线程句柄，**为的是让测试能 join** —— 否则只能靠 sleep 猜 |
| `session_manager` | `InterviewSession.score` 字段 + `snapshot()` 里带上它 |
| `score_guard` | 新增 `NOT_MENTIONED`；`verify_evidence()` 跳过它（见下） |

#### 三条纪律（写在 `_start_scoring()` 的注释里）

| 纪律 | 为什么 |
|---|---|
| **只"发起"不"等待"** | 评分要额外一次 LLM 调用（实测十几秒），而板子正阻塞等回包。放请求线程里就是把这十几秒加到板子头上 —— 违反"云端处理不能让端侧多等"这条底线 |
| **绝不改端侧响应体** | 评分只进会话快照（网页 / 导出 / 落盘）。`/api/interview` 的字段**一个不多、一个不少** |
| **失败只记日志** | 评分是锦上添花，不能影响一场已经完成的面试 |

> 第二条有单测守着：把 ASR / LLM / TTS 与评分函数**全打桩**，断言 `/api/interview`
> 的响应字段**恰好**是那 6 个。**这是本轮最要紧的一条守卫** —— 板子只解析 5 个字段、
> 缓冲 8MB，混进一大段评分文本没有任何好处。

#### 维度只有一个来源

`score_guard.DIMENSIONS`。提示词模板里写的是 `{dimensions}`、运行时注入 —— 这正是
`score_guard` 当初把 DIMENSIONS 定成"唯一事实来源"时留下的约定（见它的模块 docstring），
避免"提示词写了 5 个维度、代码只认 4 个"。**改维度要改代码，不是改那个 JSON。**

#### `NOT_MENTIONED` 是接线时才发现的

提示词要求：某维度候选人完全没提到时，`evidence` 就写「未提及」。而 `verify_evidence()`
原本会把"未提及"当成"对不上的依据"报出来 —— 一场候选人没怎么说话的面试会在日志里刷
四个"依据对不上"，**把真正的信号淹掉**。现在跳过它，并加了一条测试盯住"常量与提示词
里的措辞必须一致"（改一头忘另一头的话，这个跳过会静默失效）。

#### 验证（PC 端，不花钱）

* `test_score_guard.py` 加 2 项（`NOT_MENTIONED` 跳过 + 常量与提示词一致）
* 新增 `test_scoring.py` **12 项**：闸门的取舍（越界夹、字符串分、丢不认识的维度、
  总分自己算）、`_start_scoring` 的接线（写进会话 + 落盘、空评分不多写存档、异常静默、
  会话不存在不炸）、**端侧响应字段恰好 6 个**、评分只在报告轮发起
* 全量 **10 个测试文件全过**；无依赖档 7 过 + 3 个大声跳过

#### 真机验证（2026-09-30，花了一次钱）

Flask **必须先重启**（改的全是模块级代码，不重启不会生效），然后跑：

```bash
rehearsal.py --say-finish --rounds 3        # 3 轮，第 3 轮说「结束吧」
```

**后台评分跑完并落地了**：

| 项 | 结果 |
|---|---|
| 总分 | **32 / 100** —— 四维均值 3.25 × 10 = 32，**代码算的、与模型无关** |
| 四个维度 | 全部给出，`missing` 为空 |
| 依据 | 都是候选人原话（`检索用的是向量数据库加关键词的混合召回。` 等） |
| 导出 Markdown | 评分表 + 每维依据 + 总评，齐全 |
| 导出 JSON | `score` 字段在，total=32、4 个维度 |
| **磁盘存档** | `score.total = 32` —— **重启后评分还在** |

顺带一个实测观察：轮询第一秒就拿到了评分，**没有等**。原因是排练脚本在报告轮之后
还有几次 HTTP 调用（查历史、两次导出），那几秒足够十几秒的评分跑完。也就是说
"评分迟到"这个时序在本机 PC 场景下几乎察觉不到；但板子那条链路真按 11 轮跑时，
用户在报告播完的当下可能还看不到分数 —— 那是设计如此（评分绝不能让板子多等）。

#### 仍未（目视）验证

* ~~**网页上那张评分卡片的实际渲染**~~ —— **人眼一看就发现了问题，见 §11.33**：
  报告卡片与评分区**根本没显示出来**（顺带查出"有新消息 ↓"按钮也一直没显示过）。

---

### 11.33 展示页两个"永远显示不出来"的元素（2026-09-30，**靠人眼看出来的**）

#### 现象

P2 做完后请人打开 `http://127.0.0.1:5000/` 目视确认评分卡片 —— 结果**报告卡片和评分区都没出现**，页面只有顶部的岗位 / 轮次 / 状态和下面那段对话。

#### 排查：接口、DOM、CSS 全是对的

| 检查 | 结果 |
|---|---|
| `/api/history` 返回 `is_finished: true`、6 条消息、`score.total = 32` | ✅ |
| 服务端返回的 HTML 里有 `<div class="wrap" id="report">` | ✅ |
| `renderReport(d)` 在消息渲染**之前**被调用 | ✅（它若抛错，连消息都看不到 —— 而消息是正常的） |
| 响应头 `Cache-Control: no-cache` | ✅ 排除浏览器缓存 |

四条全对 ⇒ 问题在**渲染逻辑本身**。

#### 根因：`style.display = ""` 不是"显示"，是"清除行内样式"

```css
#report { display: none; }      /* CSS 里藏着 */
```
```js
elReport.style.display = "";    /* 清掉行内样式之后，上面那条规则重新生效 */
```

**对照组**：`#doneBadge` / `#roleBadge` / `#roundBadge` 用的是 HTML 上的
`style="display:none"`（**行内**样式），清除行内样式就能恢复默认 —— 同一个写法，
因为隐藏方式不同，结果完全相反。所以这个坑极隐蔽：**代码里到处都在用
`style.display = ""`，其中大多数是对的。**

#### 顺带查出第二个（更老）

`#jump`（"有新消息 ↓"按钮）犯的是同一个错：CSS 里 `display: none`，JS 用
`style.display = ""` 显示。**从写出来那天起就没显示过** —— 只是它只在"用户往上翻
了、又有新消息"时才该出现，一直没人注意到。

#### 修法与护栏

两处都改成给具体值：`elReport` → `"block"`，`elJump` → `"inline-block"`（button 的
默认显示值）。

**并把这条判据写成静态检查**：新增 `cloud/test_page_display.py` —— 扫 `<style>` 里按
id 藏的 `display:none`、扫 `<script>` 里 `elXxx.style.display = ""` 的写法，两者一
交集就报错；顺带检查 `getElementById` 绑的 id 是否真在页面里。

* 修复后：4 项全过。
* **对照组**：拿修复前的页面跑同一套检查 → 精确报出 `['elReport (#report)', 'elJump (#jump)']`。

**修复后用户目视确认通过**（2026-09-30）：刷新页面后卡片出现，总分与四条维度进度条渲染正常。

---

### 11.34 统一"四维度"：三套并存的历史结束（2026-10-01）

#### 起因

讨论"公共设备"路线下的前端优化时，对照 `myagent` 发现：**我们给用户的反馈自己跟自己打架**。

同一件事——"这场面试表现如何"——在三个地方用了**三套不同的维度名**：

| 位置 | 四个维度 | 性质 |
|---|---|---|
| `skills/generate_feedback.json`（**实际生效**） | 技术正确性 / 深度与原理 / 工程与场景思考 / 表达与结构 | 继承自 myagent 的方法论，**唯一有外部依据的** |
| `skills/README.md` §3.4（文档） | 逻辑性 / 专业度 / 表达清晰度 / 岗位匹配度 | 9/18 改完提示词**忘了同步文档** |
| `cloud/score_guard.py` 的 `DIMENSIONS`（评分卡） | 表达与逻辑 / 专业深度 / 项目经验 / 岗位匹配 | **9/29 在 VM 里另起的一套**，当时没人注意到前面已经有两套 |

**用户读完报告（听"技术正确性"），低头看评分卡（写"表达与逻辑"）——不是一回事。** 对一个"给用户看反馈"的产品，这比缺功能更伤。

#### 怎么统一的

统一到**报告那套**（三者中唯一有出处的，而且已经在提示词里生效）：

* `score_guard.DIMENSIONS` 改**一处** —— 评分提示词由它注入（`{dimensions}` 占位符）**自动跟随**，这正是当初把它定为"唯一事实来源"的用意
* `skills/README.md` §3.4 的错描述改成与实际提示词一致
* `cloud/README.md` §3.9、根 README §4.2.1 的维度清单同步
* 5 个测试文件里的样本按**位置一一对应**替换（表达与逻辑→技术正确性、专业深度→深度与原理、项目经验→工程与场景思考、岗位匹配→表达与结构）
* **不动 `cloud/data/sessions/` 里的历史会话** —— 那是记录，改了就篡改历史；页面是动态读 `dim.name` 渲染的，老数据不会报错，只是保留当时的维度名

#### 收益

报告念的四个维度 = 卡片上的四条进度条，**一一对应**。听到"技术正确性"，低头看到的是同一个词。

#### 验证

* 全量 `run_tests.sh`：**11 个文件全过**（覆盖评分闸门、评分接线、导出渲染、报告闸门）
* **真机验证通过**（2026-10-01，花了一次钱）：Flask 重启后跑
  `rehearsal.py --rounds 2 --say-finish`，后台评分拿到的维度名是

  ```
  ['技术正确性', '深度与原理', '工程与场景思考', '表达与结构']
  ```

  与代码里的 `DIMENSIONS` **完全一致**，且 `missing` 为空（没有任何维度被闸门丢掉）。

  同一场的**报告正文**是："…技术正确性未涉及，深度与原理未涉及，工程与场景思考未涉及，
  表达与结构…" —— **听到的和看到的终于是同一套词**。

  > 这条为什么要花一次钱验：维度名换了之后，若模型仍返回旧名字，闸门会把它们当
  > "不认识的维度"丢掉，最终表现是**"这场没有评分"而不是报错** —— 又一个静默失败。
  > 现在可以确定不会了。

#### 一条说明

`岗位匹配` 这个维度在本次统一里**被去掉了**（报告那六句里没有它）。以后想加回来，必须**同时**加到报告的六句结构和评分维度里 —— 只加一边，就又变成两套了。

> 为什么只能静态检查：本项目没有可用的无头浏览器（§11.25 遗留确认过 chromium
> 不可用）。它能拦住**写法错误**，**拦不住**布局 / 配色 / 遮挡那类只有肉眼才看得出
> 的问题 —— 所以"打开浏览器看一眼"这一步仍然不能省。**这次就是靠人眼发现的。**

#### 教训

**"字段对得上、DOM 在、CSS 写了"都不等于"看着对"。**
P1 那批网页改动（报告卡片 + 两个下载按钮）当时只验了 `/api/export` 的 HTTP 200，
**从没有人真正打开页面看过** —— 于是卡片一直不显示也没人发现（§11.25 的"证据"
里写的也是导出接口 200，不是"页面显示正常"）。
**凡是"用户要看的界面"，验收标准只能是"人看到了"。**
