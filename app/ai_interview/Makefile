############################################################################
# app/ai_interview/Makefile
#
# AI模拟面试官 — OpenVela 构建文件
############################################################################

include $(APPDIR)/Make.defs

# 应用配置
PROGNAME  = $(CONFIG_APP_AI_INTERVIEW_PROGNAME)
PRIORITY  = $(CONFIG_APP_AI_INTERVIEW_PRIORITY)
STACKSIZE = $(CONFIG_APP_AI_INTERVIEW_STACKSIZE)
MODULE    = $(CONFIG_APP_AI_INTERVIEW)

# 源文件列表
MAINSRC   = main.c
CSRCS     = state_machine.c network_client.c audio_io.c

# 依赖的头文件路径。
#
# 注意 audio/ 目录不在 CSRCS 里：那 6 个 .c 与 vendor 树里的 hal/test/sound/
# 逐字节相同，而该目录已由 CONFIG_COMPONENTS_AW_ALSA_UTILS 编进 libapps.a
# （nm 可见 aplay / capture_fs_wav / set_param / create_wav / pcm_read 等符号）。
# 再编一份会造成重复定义，且归档链接的符号解析顺序不可预测。
# 我们只通过 audio/common.h 声明引用它们，不重复编译。
CFLAGS += ${INCDIR_PREFIX}$(APPDIR)/../external/curl/curl/include
CFLAGS += ${INCDIR_PREFIX}$(APPDIR)/crypto/mbedtls/mbedtls/include

# audio_io.c 需要 vendor 的 ALSA 头（aw-alsa-lib/pcm.h 及其依赖的 osal 头）。
# 路径写法与 vendor 自己那份 hal/test/sound/Makefile 同构。
# $(APPDIR)/vendor 是 apps/vendor -> ../vendor 软链。
CFLAGS += ${INCDIR_PREFIX}$(APPDIR)/vendor/allwinnertech/chips/r528/drivers/rtos-hal/include/hal
CFLAGS += ${INCDIR_PREFIX}$(APPDIR)/vendor/allwinnertech/chips/r528/drivers/rtos-hal/include/osal

include $(APPDIR)/Application.mk
