# ##############################################################################
# app/ai_interview_test/CMakeLists.txt
# ##############################################################################

if(CONFIG_APP_AI_INTERVIEW_TEST)
  nuttx_add_application(
    NAME
    ${CONFIG_APP_AI_INTERVIEW_TEST_PROGNAME}
    SRCS
    ai_interview_test_main.c
    STACKSIZE
    ${CONFIG_APP_AI_INTERVIEW_TEST_STACKSIZE}
    PRIORITY
    ${CONFIG_APP_AI_INTERVIEW_TEST_PRIORITY})
endif()
