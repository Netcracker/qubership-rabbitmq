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

Change Rabbitmq Password Through Operator
    [Arguments]  ${username}  ${password}

    Change Rabbitmq Password With Operator  ${username}  ${password}
    Sleep  15s
    ${secret}=  Get Secret  rabbitmq-default-secret  ${NAMESPACE}
    ${current_password}=  Get Password From Secret  ${secret}
    Should Be Equal As Strings  ${current_password}  ${password}
    ${alive}=  Is Rabbit Alive With Password  ${password}
    Should Be True  ${alive}

Change Rabbitmq Password Through Function
    [Arguments]  ${pod_name}  ${password}

    Change Rabbitmq Password With Function  ${pod_name}  ${password}
    Sleep  15s
    ${secret}=  Get Secret  rabbitmq-default-secret  ${NAMESPACE}
    ${current_password}=  Get Password From Secret  ${secret}
    Should Be Equal As Strings  ${current_password}  ${password}
    ${alive}=  Is Rabbit Alive With Password  ${password}
    Should Be True  ${alive}

Change Rabbitmq Password With Operator Teardown
    [Arguments]  ${pod_name}  ${old_password}  ${secret_change}

    Change Rabbitmq Password With Function  ${pod_name}  ${old_password}
    Set Secret Change Field  ${secret_change}

*** Test Cases ***
Test Change Rabbitmq Password With Operator
    [Tags]  change_password  all  operator_change_password

    ${pod_name}=  Get First Rabbit Pod
    ${secret}=  Get Secret  rabbitmq-default-secret  ${NAMESPACE}
    ${old_password}=  Get Password From Secret  ${secret}
    ${old_secret_change}=  Get Secret Change Value

    Change Rabbitmq Password Through Operator  admin  ${NEW_PASS}

    Change Rabbitmq Password Through Operator  admin  ${old_password}

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

    [Teardown]  Change Rabbitmq Password With Function  ${pod_name}  ${old_password}

Test Change Password Function With Kill All Pods
    [Tags]  persistence  all

    ${secret}=  Get Secret  rabbitmq-default-secret  ${NAMESPACE}
    ${old_password}=  Get Password From Secret  ${secret}

    ${pod_name}=  Get First Rabbit Pod

    Change Rabbitmq Password Through Function  ${pod_name}  ${NEW_PASS}

    Force Kill All Pods  ${pod_names}  at_once
    ${alive}  Is Rabbit Alive With Password  ${NEW_PASS}
    Should Be True  ${alive}
    ${pod_name}=  Get First Rabbit Pod

    Change Rabbitmq Password Through Function  ${pod_name}  ${old_password}

    [Teardown]  Change Rabbitmq Password With Function  ${pod_name}  ${old_password}

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
