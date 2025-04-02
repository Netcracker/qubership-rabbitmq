*** Variables ***

${RABBITMQ_HOST}    %{RABBITMQ_HOST}
${RABBITMQ_PORT}    %{RABBITMQ_PORT}
${AMQP_PORT}        %{AMQP_PORT}
${RMQUSER}          %{RMQUSER}
${RMQPASSWORD}      %{RMQPASSWORD}
${TIMEOUT}          10
${TEST_USER}        robottestuser
${TEST_VHOST}       robottestvhost
${TEST_QUEUE}       testQueue
${TEST_PASSWORD}    123456
${NEW_PASS}         testpassword
${NAMESPACE}        %{NAMESPACE}
${RABBIT_IS_MANAGED_BY_OPERATOR}    %{RABBIT_IS_MANAGED_BY_OPERATOR}
${RABBITMQ_BACKUP_DAEMON}    %{RABBITMQ_BACKUP_DAEMON=rabbitmq-backup-daemon}

*** Settings ***

Library           PlatformLibrary  managed_by_operator=%{RABBIT_IS_MANAGED_BY_OPERATOR}
Library           Collections
Library           String
Library           ./lib/NCRabbitMQLibrary.py  host=${RABBITMQ_HOST}
...               port=${RABBITMQ_PORT}
...               rmquser=${RMQUSER}
...               rmqpassword=${RMQPASSWORD}
...               timeout=${TIMEOUT}
...               backuper_host=${RABBITMQ_BACKUP_DAEMON}
...               managed_by_operator=${RABBIT_IS_MANAGED_BY_OPERATOR}
Library           ./lib/CloudResourcesLibrary.py

*** Keywords ***

Preparation Test Data
    Get All Rabbit Pods

Get All Rabbit Pods
    ${rabbit_pods}=  Get Pods  ${NAMESPACE}
    ${pod_names}=  Get Pods By Mask  ${rabbit_pods}  rmqlocal
    Set Suite Variable  ${pod_names}

Cleanup Test Data
    Delete User If Exist
    Delete Vhost If Exist
    Delete Queue If Exist
    Run Keyword And Ignore Error  Close All Rabbitmq Connections

Delete User If Exist
    ${status}=  Run Keyword And Return Status  Check User
    Run Keyword If  '${status}'=='True'  Clean User

Delete Vhost If Exist
    ${status}=  Run Keyword And Return Status  Check Vhost
    Run Keyword If  '${status}'=='True'  Clean Vhost

Delete Queue If Exist
    ${status}=  Queue Exist  ${TEST_VHOST}  ${TEST_QUEUE}
    Run Keyword If  '${status}'=='True'  Delete Queue  ${TEST_VHOST}  ${TEST_QUEUE}

Clean User
    Delete Test User  ${TEST_USER}
    ${users}=  Get Users
    Should Not Contain  ${users}  ${TEST_USER}

Clean Vhost
    ${r}=  Delete Vhost  ${TEST_VHOST}
    ${vhosts}=  Get Vhosts
    Should Not Contain  ${vhosts}  ${TEST_VHOST}

Check User
    ${users}=   Get Users
    Should Contain  ${users}    ${TEST_USER}

Check Vhost
    ${vhosts}=  Get Vhosts
    Should Contain  ${vhosts}   ${TEST_VHOST}

Create And Check Queue
    NCRabbitMQLibrary.Create Queue    vhost=${TEST_VHOST}  queue=${TEST_QUEUE}  node_number=${0}
    ${exist}=  Queue Exist  ${TEST_VHOST}  ${TEST_QUEUE}
    Should Be True  ${exist}

Check Cluster
    [Arguments]  ${replicas}
    ${alive}=  Is Rabbit Alive
    Should Be True  ${alive}

    ${alive}=  Is Cluster Alive  ${replicas}
    Should Be True  ${alive}

Delete And Check Queue
    NCRabbitMQLibrary.Delete Queue  ${TEST_VHOST}  ${TEST_QUEUE}

    ${exist}=  Queue Exist  ${TEST_VHOST}  ${TEST_QUEUE}
    Should Not Be True  ${exist}

Set Replicas
    [Arguments]  ${count}
    Set Stateful Set Replicas  rmqlocal  ${count}
    ${number}=  Get Rabbitmq Ready Replicas
    Should Be Equal As Integers  ${count}  ${number}

Change Rabbitmq Password With Function
    [Arguments]  ${pod_name}  ${password}
    ${result}  ${error}=  Execute Command In Pod  ${pod_name}  ${NAMESPACE}
    ...  change_password $RABBITMQ_DEFAULT_USER ${password}
    Log  result: ${result} error: ${error}
    Sleep  10s

Get First Rabbit Pod
    ${rabbit_pods}=  Get Pods  ${NAMESPACE}
    ${pod_names}=  Get Pods By Mask  ${rabbit_pods}  rmqlocal
    [Return]  ${pod_names[0]}

Get Rabbit Replicas From Single Stateful Set
    [Arguments]  ${stateful_set_names}
    ${stateful_set_names}=  Set Variable  ${stateful_set_names[0]}
    ${replicas}=  Get Stateful Set Replicas Count  ${stateful_set_names}  ${NAMESPACE}
    [Return]  ${replicas}
