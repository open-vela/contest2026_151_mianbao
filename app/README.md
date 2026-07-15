# AI模拟面试官 — 应用程序目录

> 更新时间：2026-07-13

---

## 📁 目录结构

```
app/
├── ai_interview/           # 主应用程序
│   ├── main.c             # 主程序入口
│   ├── state_machine.c    # 状态机实现
│   ├── state_machine.h    # 状态机头文件
│   ├── network_client.c   # 网络通信模块
│   ├── Makefile           # 构建配置
│   ├── Kconfig            # 内核配置
│   ├── Make.defs          # 构建定义
│   └── CMakeLists.txt     # CMake 配置
│
├── ai_interview_test/      # ✅ 集成测试程序
│   ├── ai_interview_test_main.c
│   ├── Makefile
│   ├── Kconfig
│   ├── Make.defs
│   └── CMakeLists.txt
│
└── README.md               # 本文件
```

---

## ✅ 集成测试程序

### 用途

`ai_interview_test` 用于验证：
1. 符号链接是否正常工作
2. 构建系统是否正确集成
3. 仓库代码是否能成功编译到开发板

### 编译和运行

```bash
# 1. 进入编译目录
cd ~/vela-opensource/vendor/allwinnertech/lichee

# 2. 激活环境
source vela_env.sh
source envsetup.sh

# 3. 选择目标板
lunch_nuttx  # 选择 r528s3-velaevb1

# 4. 配置（可选）
menuconfig  # 在 Examples 中启用 AI Interview Integration Test

# 5. 编译
m

# 6. 打包
pack

# 7. 烧录到开发板后，在串口 NSH 中运行：
nsh> ai_interview_test
```

### 预期输出

```
========================================
  AI模拟面试官 - 集成测试 v1.0
  队伍: mianbao (contest2026_151)
========================================

[TEST 1] 符号链接验证
  ✅ 如果你能看到这条消息，说明符号链接工作正常
  ✅ 代码来自 GitHub 仓库目录

[TEST 2] 构建系统验证
  ✅ Makefile 已正确配置
  ✅ Kconfig 已正确注册
  ✅ 应用已成功编译为 NSH 内置命令

[TEST 3] 硬件平台信息
  📱 目标板: 全志 R528 (T113S3)
  🖥️  开发板: DshanPI openvela Devkit
  📺 屏幕: 3.5寸 LCD

[TEST 4] 功能模块状态
  ✅ 状态机 (state_machine.c) - 已实现
  ⏳ 网络通信 (network_client.c) - 待实现
  ⏳ 音频采集 - 待集成
  ⏳ 云端服务 - 待对接

========================================
  🎉 集成测试完成！
  下一步: 实现完整的 AI 面试功能
========================================
```

---

## 🔗 符号链接说明

编译系统通过符号链接访问仓库代码：

```
/home/ubuntu/vela-opensource/apps/examples/ai_interview_test
    → /home/ubuntu/openvela_contest/contest2026_151_mianbao/app/ai_interview_test
```

**优势**：
- ✅ 代码留在 GitHub 仓库目录（便于版本控制）
- ✅ 修改后无需同步复制
- ✅ 组员可以直接克隆仓库开发

---

## 📝 添加新应用

如需添加新的应用模块：

1. 在 `app/` 下创建新目录
2. 添加源代码和构建文件（Makefile, Kconfig, Make.defs, CMakeLists.txt）
3. 创建符号链接：
   ```bash
   ln -s /home/ubuntu/openvela_contest/contest2026_151_mianbao/app/你的应用 \
         /home/ubuntu/vela-opensource/apps/examples/你的应用
   ```
4. 注册到 Kconfig：
   ```bash
   sed -i '/^endmenu/i source "/home/ubuntu/vela-opensource/apps/examples/你的应用/Kconfig"' \
       /home/ubuntu/vela-opensource/apps/examples/Kconfig
   ```

---

## 负责人

- **A同学**：云端服务、网络通信
- **B同学**：端侧开发、状态机
- **C同学**：数据收集、Prompt 优化
