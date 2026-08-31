*** Settings ***

Resource        ../keywords.robot
Suite Setup     Preparation Test Persistence Data
Suite Teardown  Cleanup Test Data

*** Keywords ***

Preparation Test Persistence Data
    Get All Rabbit Pods
    Create Rabbitmq Connection  ${RABBITMQ_HOST}  ${RABBITMQ_PORT}  ${AMQP_PORT}
    ...  ${rmquser}  ${rmqpassword}  alias=rmq  vhost=/

Kill All Pods
    [Arguments]  ${pod_names}  ${order}

    ${alive}    Is Rabbit Alive
    Should Be True   ${alive}

    ${r}  Create Test User And Vhost  ${TEST_USER}  ${TEST_PASSWORD}  ${TEST_VHOST}
    # Creation of a vhost takes some time
    Sleep  15s

    Create Rabbitmq Connection  ${RABBITMQ_HOST}  ${RABBITMQ_PORT}  ${AMQP_PORT}  ${TEST_USER}
    ...  ${TEST_PASSWORD}  alias=rmq  vhost=${TEST_VHOST}

    ${overview}=  Overview
    Should Not Be Equal  ${overview}  ${None}

    Create And Check Queue

    Force Kill All Pods  ${pod_names}  ${order}

    ${replicas}=  Get Rabbitmq Replicas
    Check Cluster  ${replicas}

    Check User
    Check Vhost
    Create Rabbitmq Connection  ${RABBITMQ_HOST}  ${RABBITMQ_PORT}  ${AMQP_PORT}  ${TEST_USER}
    ...  ${TEST_PASSWORD}  alias=rmq  vhost=${TEST_VHOST}

    ${overview}=  Overview
    Should Not Be Equal  ${overview}  ${None}

    Delete And Check Queue
    Clean User
    Clean Vhost

Verify Password Applied
    [Arguments]  ${password}
    ${secret}=  Get Secret  rabbitmq-default-secret  ${NAMESPACE}
    ${current_password}=  Get Password From Secret  ${secret}
    Should Be Equal As Strings  ${current_password}  ${password}
    ${alive}=  Check Management Auth With Password  ${password}
    Should Be True  ${alive}

Verify RabbitMQ Accepts Password
    [Arguments]  ${password}
    ${alive}=  Check Management Auth With Password  ${password}
    Should Be True  ${alive}

Change Rabbitmq Password Through Operator
    [Arguments]  ${username}  ${password}

    Change Rabbitmq Password With Operator  ${username}  ${password}
    Wait Until Keyword Succeeds  20 min  15 s  Verify Password Applied  ${password}

Change Rabbitmq Password Through Function
    [Arguments]  ${pod_name}  ${password}  ${timeout}=120s

    Change Rabbitmq Password With Function  ${pod_name}  ${password}
    Wait Until Keyword Succeeds  ${timeout}  5s  Verify RabbitMQ Accepts Password  ${password}

Change Rabbitmq Password Through Function And Verify
    [Arguments]  ${pod_name}  ${password}  ${timeout}=5 min

    Change Rabbitmq Password With Function  ${pod_name}  ${password}
    Wait Until Keyword Succeeds  ${timeout}  15 s  Verify Password Applied  ${password}

Change Rabbitmq Password With Operator Teardown
    [Arguments]  ${pod_name}  ${old_password}  ${secret_change}

    Run Keyword If  '${pod_name}' != '${EMPTY}' and '${old_password}' != '${EMPTY}'
    ...  Run Keyword And Ignore Error  Change Rabbitmq Password With Function  ${pod_name}  ${old_password}
    Run Keyword If  '${secret_change}' != '${EMPTY}'
    ...  Run Keyword And Ignore Error  Set Secret Change Field  ${secret_change}

Change Rabbitmq Password With Function Teardown
    [Arguments]  ${pod_name}  ${old_password}
    Change Rabbitmq Password With Function  ${pod_name}  ${old_password}
    Wait Until Keyword Succeeds  120s  5s  Verify RabbitMQ Accepts Password  ${old_password}

*** Test Cases ***
Test Change Rabbitmq Password With Operator
    [Tags]  change_password  all  operator_change_password

    Set Test Variable  ${pod_name}  ${EMPTY}
    Set Test Variable  ${old_password}  ${EMPTY}
    Set Test Variable  ${old_secret_change}  ${EMPTY}
    ${pod_name}=  Get First Rabbit Pod
    ${secret}=  Get Secret  rabbitmq-default-secret  ${NAMESPACE}
    ${username}=  Get User From Secret  ${secret}
    ${old_password}=  Get Password From Secret  ${secret}
    ${old_secret_change}=  Get Secret Change Value

    Change Rabbitmq Password Through Operator  ${username}  ${NEW_PASS}

    Change Rabbitmq Password Through Operator  ${username}  ${old_password}

    [Teardown]  Change Rabbitmq Password With Operator Teardown  ${pod_name}  ${old_password}  ${old_secret_change}

Test Change Password Function
    [Tags]  change_password  all

    ${alive}  Is Rabbit Alive
    Should Be True  ${alive}
    ${secret}=  Get Secret  rabbitmq-default-secret  ${NAMESPACE}
    ${old_password}=  Get Password From Secret  ${secret}
    ${pod_name}=  Get First Rabbit Pod

    Change Rabbitmq Password Through Function  ${pod_name}  ${NEW_PASS}

    Change Rabbitmq Password Through Function  ${pod_name}  ${old_password}

    [Teardown]  Change Rabbitmq Password With Function Teardown  ${pod_name}  ${old_password}

Test Change Password Function With Kill All Pods
    [Tags]  persistence  all

    Wait For RabbitMQ Pods Ready
    ${secret}=  Get Secret  rabbitmq-default-secret  ${NAMESPACE}
    ${old_password}=  Get Password From Secret  ${secret}

    ${pod_name}=  Get First Rabbit Pod

    Wait Until Keyword Succeeds  5 min  15 s  Verify Password Applied  ${old_password}

    Change Rabbitmq Password Through Function And Verify  ${pod_name}  ${NEW_PASS}

    Force Kill All Pods  ${pod_names}  at_once
    Wait For RabbitMQ Pods Ready
    Wait Until Keyword Succeeds  5 min  15 s  Verify Password Applied  ${NEW_PASS}
    ${pod_name}=  Get First Rabbit Pod

    Change Rabbitmq Password Through Function And Verify  ${pod_name}  ${old_password}

    [Teardown]  Change Rabbitmq Password With Function Teardown  ${pod_name}  ${old_password}

Kill All Pods At Once
    [Tags]  persistence  all

    Kill All Pods  ${pod_names}  at_once

Kill All Pods Order By Asc Order
    [Tags]  persistence  all

    Kill All Pods  ${pod_names}  asc

Kill All Pods Order By Desc
    [Tags]  persistence  all

    Kill All Pods  ${pod_names}  desc

Kill Part Of Pods
    [Tags]  persistence  all

    Kill All Pods  ${pod_names}  part
