*** Settings ***

Resource          ../keywords.robot

Suite Setup    Preparation Test Data
Suite Teardown  Cleanup Test Data

*** Test Cases ***

Test Cluster
    [Tags]  smoke  cluster  all

    ${alive}=  Is Rabbit Alive
    Should Be True  ${alive}
    ${replicas}=  Get Rabbitmq Replicas

    ${alive}=  Is Cluster Alive  ${replicas}
    Should Be True  ${alive}

Test Connection
    [Tags]  smoke  all

    ${alive}=  Is Rabbit Alive

    Create Rabbitmq Connection  ${RABBITMQ_HOST}  ${RABBITMQ_PORT}  ${AMQP_PORT}
    ...  ${rmquser}  ${rmqpassword}  alias=rmq  vhost=/
    ${overview}=  Overview
    Should Not Be Equal  ${overview}  ${None}

Create Queue, User And Vhost
    [Tags]  smoke  all
    ${alive}=  Is Rabbit Alive
    Should Be True  ${alive}
    Create Test User And Vhost  ${TEST_USER}  ${TEST_PASSWORD}  ${TEST_VHOST}
    Create Rabbitmq Connection  ${RABBITMQ_HOST}  ${RABBITMQ_PORT}  ${AMQP_PORT}  ${TEST_USER}
     ...  ${TEST_PASSWORD}  alias=rmq  vhost=${TEST_VHOST}
    ${overview}=  Overview
    Should Not Be Equal  ${overview}  ${None}
    Create And Check Queue
    Delete And Check Queue
    Clean User
    Clean Vhost