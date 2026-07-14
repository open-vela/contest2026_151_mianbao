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

include $(APPDIR)/Application.mk
