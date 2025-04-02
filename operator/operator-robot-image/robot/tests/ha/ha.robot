
*** Settings ***

Resource        ../keywords.robot
Suite Setup     Preparation Test Data
Suite Teardown  Cleanup HA Test Data

*** Keywords ***

Cleanup HA Test Data
    Start Node If Stopped  ${first_pod}
    Delete User If Exist
    Delete Vhost If Exist
    Delete Queue If Exist
    Run Keyword And Ignore Error  Close All Rabbitmq Connections

Start Node If Stopped
    [Arguments]  ${pod}
    ${node_status}  ${err}  Execute Command In Pod  ${pod}  ${NAMESPACE}
    ...  rabbitmqctl status
    ${state}=  Run Keyword And Return Status  Should Contain
    ...  ${node_status}  Runtime
    Run Keyword If  '${state}'=='False'  Start Node  ${pod}

Kill All Pods w/o Data
    [Arguments]  ${pod_names}  ${order}

    ${alive}  Is Rabbit Alive
    Should Be True  ${alive}

    Force Kill All Pods  ${pod_names}  ${order}

    ${replicas}=  Get Rabbitmq Replicas
    Check Cluster  ${replicas}

*** Test Cases ***

Kill All Pods At Once w/o Data
    [Tags]  ha  all
    Kill All Pods w/o Data  ${pod_names}  at_once

Kill All Pods By Asc w/o Data
    [Tags]  ha  all

    Kill All Pods w/o Data  ${pod_names}  asc

Kill All Pods By Desc w/o Data
    [Tags]  ha  all

    Kill All Pods w/o Data  ${pod_names}  desc

Kill Part Of Pods w/o Data
    [Tags]  ha  all

    Kill All Pods w/o Data  ${pod_names}  part

HA Queue Test
    [Tags]  ha  all

    ${first_pod}=  Get First Rabbit Pod
    Set Suite Variable  ${first_pod}

    Create Rabbitmq Connection  ${RABBITMQ_HOST}  ${RABBITMQ_PORT}  ${AMQP_PORT}
    ...  ${rmquser}  ${rmqpassword}  alias=rmq  vhost=/

    ${alive}=  Is Rabbit Alive
    Should Be True  ${alive}

    Create Test User And Vhost  ${TEST_USER}  ${TEST_PASSWORD}  ${TEST_VHOST}
    # Creation of a vhost takes some time
    Sleep  5s

    Create Rabbitmq Connection  ${RABBITMQ_HOST}  ${RABBITMQ_PORT}  ${AMQP_PORT}  ${TEST_USER}
    ...  ${TEST_PASSWORD}  alias=rmq  vhost=${TEST_VHOST}
    ${overview}=  Overview
    Log Dictionary  ${overview}

    ${resutl}  ${err}  Set Policy Ha All  ${first_pod}  ${TEST_VHOST}
    Should Be Empty  ${err}
    Create And Check Queue

    Publish Msg  ${TEST_VHOST}  ${TEST_QUEUE}

    ${result}  ${err}  Stop Node  ${first_pod}
    Should Be Empty  ${err}

    ${exist}=  Queue Exist  ${TEST_VHOST}  ${TEST_QUEUE}
    Should Be True  ${exist}
    ${msg}  Get Msg  ${TEST_VHOST}  ${TEST_QUEUE}
    Should Not Be Empty  ${msg}
    ${queue}  Get Queue From Msg  ${msg}
    Should Be Equal  ${queue}  ${TEST_QUEUE}

    ${result}  ${err}  Start Node  ${first_pod}
    Should Be Empty  ${err}

    ${replicas}=  Get Rabbitmq Replicas
    Check Cluster  ${replicas}

    Delete And Check Queue
    Clean User
    Clean Vhost