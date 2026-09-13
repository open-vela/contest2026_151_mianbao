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
CSRCS     = state_machine.c network_client.c

# network_client.c 依赖的头文件路径。
# 注意 audio/ 目录不在此列：那 6 个文件与 vendor 树里的 hal/test/sound/ 逐字节
# 相同，而该目录已由 CONFIG_COMPONENTS_AW_ALSA_UTILS 编进 libapps.a
# （aplay / capture_fs_wav / set_param / create_wav 等符号已存在）。
# 再编一份会造成重复定义，且归档链接的解析顺序不可预测。
CFLAGS += ${INCDIR_PREFIX}$(APPDIR)/../external/curl/curl/include
CFLAGS += ${INCDIR_PREFIX}$(APPDIR)/crypto/mbedtls/mbedtls/include

include $(APPDIR)/Application.mk
