# ##############################################################################
# app/ai_interview/CMakeLists.txt
# ##############################################################################

if(CONFIG_APP_AI_INTERVIEW)
  nuttx_add_application(
    NAME
    ${CONFIG_APP_AI_INTERVIEW_PROGNAME}
    SRCS
    main.c
    state_machine.c
    network_client.c
    STACKSIZE
    ${CONFIG_APP_AI_INTERVIEW_STACKSIZE}
    PRIORITY
    ${CONFIG_APP_AI_INTERVIEW_PRIORITY})
endif()
