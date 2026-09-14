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
| 2 | 定静音阈值与麦克风增益 | ✅ 已完成：门限 **500**、增益 **×4**，实测依据见 11.8 |
| 3 | 推送未推送的 commit | ✅ 已完成（9/14）：10 个提交已推送至 `openvela/dev-ai-contest-2026`，远端与本机一致 |
| 4 | 复核云端响应 8MB 上限 —— 纯静音那轮触发了 `响应超过上限 8388608 字节` | ⏳ 待观察。近期各轮解码后 253KB~975KB，余量充足，但**仍未正面确认** |
| 5 | R3 修正文档（`project_status.md` 描述了 4 个不存在的文件） | ✅ 已完成（9/14）：详见 **§11.10** |
| 6 | R4 重写 README（评委据此复现，**含编译命令定论**） | ✅ 已完成（9/14）：README 已按组委会模板重写；编译命令定论见 **§11.9** |
| 7 | R5-R7 清理（`logs/your-github-login/`、12 个被跟踪的构建产物） | ✅ 已完成（9/14）：共摘除 16 个文件，详见 **§11.11** |
| 8 | 演示排练（多轮对话 + Wi-Fi 稳定性） | ☐ 未开始 |
| 9 | 演示前最后一次轮换 MIMO key（旧 key 已进过远端历史） | ☐ 未开始 |
| 10 | 上板验证「断电重启后板子会不会自动连回热点」 | ☐ 未开始，见 11.7 |

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
export MIMO_API_KEY="$(cat ~/.mimo_key)"
python3 app.py
```

> **先把 key 存下来**（仓库之外，绝不可能被提交）：
> ```bash
> nano ~/.mimo_key        # 用编辑器粘贴 key，只留一行
> chmod 600 ~/.mimo_key
> ```
> 用编辑器而不是 `export`，是为了不让 key 落进 shell history。
>
> 启动成功时 Flask 会打印 `API Key: sk-xxxxxxxxxx...`（前 10 位）—— **看到它才算读到了**。
>
> **忘了设的典型症状**：HTTP 200，但端侧报 `tts_audio 为空（云端多半缺 API key）`。见到这条先查 key，别去查网络。

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

#### 尚未验证的两件事

1. **板子上电后会不会自动连回热点** —— 没测过。**下次上板请先断电重启一次，直接 `ifconfig` 看**。这一条决定了上面那段重连命令是不是每次都得敲。
2. **`wapi power_save wlan0 off` 是否真能消除掉线** —— 关掉之后要连续跑几轮才看得出来。

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
