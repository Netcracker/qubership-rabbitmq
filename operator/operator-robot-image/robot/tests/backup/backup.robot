*** Settings ***

Resource          ../keywords.robot

Suite Setup    Preparation Test Data
Suite Teardown  Cleanup Test Data

*** Variables ***
${ITERATIONS}                1000

*** Test Cases ***
Check RabbitMQ Backup Endpoints
    [Tags]  backup  backup_daemon_endpoints  all
    ${alive}  Is Rabbit Alive
    Should Be True  ${alive}

    ${response}=  Check Backup Health
    Should Be True  ${response}

    Create Test User And Vhost  ${TEST_USER}  ${TEST_PASSWORD}  ${TEST_VHOST}
    # Creation of a vhost takes some time
    sleep  ${TIMEOUT}
    Create Rabbitmq Connection  ${RABBITMQ_HOST}  ${RABBITMQ_PORT}  ${AMQP_PORT}  ${TEST_USER}  ${TEST_PASSWORD}  alias=rmq  vhost=${TEST_VHOST}
    Create and check queue
    ${backup_folder}  Make Rabbitmq Full Backup
    Wait Job Success  job_name=${backup_folder}

    ${response}=  Check List Of Backups
    Should Contain  ${response}  ${backup_folder}

    ${response}=  Check Backup Information  vault_name=${backup_folder}
    ${found_word}=  Set Variable  "id": "${backup_folder}", "failed": false
    Should Contain  ${response}  ${found_word}

    Evict Vault  vault_name=${backup_folder}
    Delete and check queue
    Clean User
    Clean Vhost

Full Backup And Restore
    [Tags]  backup  full_backup  all
    ${alive}  Is Rabbit Alive
    Should Be True  ${alive}

    Create Test User And Vhost  ${TEST_USER}  ${TEST_PASSWORD}  ${TEST_VHOST}
    # Creation of a vhost takes some time
    sleep  ${TIMEOUT}
    Create Rabbitmq Connection  ${RABBITMQ_HOST}  ${RABBITMQ_PORT}  ${AMQP_PORT}  ${TEST_USER}  ${TEST_PASSWORD}  alias=rmq  vhost=${TEST_VHOST}
    Create and check queue
    ${backup_folder}  Make Rabbitmq Full Backup
    Wait Job Success  job_name=${backup_folder}
    Delete and check queue
    Clean User
    Clean Vhost

    ${restore_name}  Make Rabbitmq Full Restore  vault_name=${backup_folder}
    Wait Job Success  job_name=${restore_name}
    Evict Vault  vault_name=${backup_folder}
    Create Rabbitmq Connection  ${RABBITMQ_HOST}  ${RABBITMQ_PORT}  ${AMQP_PORT}  ${TEST_USER}  ${TEST_PASSWORD}  alias=rmq  vhost=${TEST_VHOST}
    ${exist}=  Queue Exist  ${TEST_VHOST}  ${TEST_QUEUE}
    Should Be True  ${exist}
    Delete and check queue
    Clean User
    Clean Vhost

Granular Backup And Restore
     [Tags]  backup  granular_backup  all
     ${alive}  Is Rabbit Alive
     Should Be True  ${alive}

     Create Test User And Vhost  ${TEST_USER}  ${TEST_PASSWORD}  ${TEST_VHOST}
     # Creation of a vhost takes some time
     sleep  ${TIMEOUT}
     Create Rabbitmq Connection  ${RABBITMQ_HOST}  ${RABBITMQ_PORT}  ${AMQP_PORT}  ${TEST_USER}  ${TEST_PASSWORD}  alias=rmq  vhost=${TEST_VHOST}
     Create and check queue
     ${backup_folder}  Make Rabbitmq Granular Backup  vhost=${TEST_VHOST}
     Wait Job Success  job_name=${backup_folder}
     Delete and check queue

     ${restore_name}  Make Rabbitmq Granular Restore  vault_name=${backup_folder}  vhost=${TEST_VHOST}
     Wait Job Success  job_name=${restore_name}
     Evict Vault  vault_name=${backup_folder}
     Create Rabbitmq Connection  ${RABBITMQ_HOST}  ${RABBITMQ_PORT}  ${AMQP_PORT}  ${TEST_USER}  ${TEST_PASSWORD}  alias=rmq  vhost=${TEST_VHOST}
     ${exist}=  Queue Exist  ${TEST_VHOST}  ${TEST_QUEUE}
     Should Be True  ${exist}
     Delete and check queue
     Clean User
     Clean Vhost

Not Evictable Backup
    [Tags]  backup  not_evictable_backup  all
    ${alive}  Is Rabbit Alive
    Should Be True  ${alive}

    Create Test User And Vhost  ${TEST_USER}  ${TEST_PASSWORD}  ${TEST_VHOST}
    # Creation of a vhost takes some time
    sleep  ${TIMEOUT}
    Create Rabbitmq Connection  ${RABBITMQ_HOST}  ${RABBITMQ_PORT}  ${AMQP_PORT}  ${TEST_USER}  ${TEST_PASSWORD}  alias=rmq  vhost=${TEST_VHOST}
    Create Queue    vhost=${TEST_VHOST}  queue=${TEST_QUEUE}  node_number=${0}
    ${backup_folder}  Make Rabbitmq Not Evictable Backup
    Wait Job Success  job_name=${backup_folder}

    ${response}=  Check Backup Information  vault_name=${backup_folder}
    ${found_word}=  Set Variable  "evictable": false
    Should Contain  ${response}  ${found_word}

    Evict Vault  vault_name=${backup_folder}
    Delete and check queue
    Clean User
    Clean Vhost

Granular Backup With A Lot Of Queues
    [Tags]  backup  granular_backup_bulk  all
    ${alive}  Is Rabbit Alive
    Should Be True  ${alive}

    Create Test User And Vhost  ${TEST_USER}  ${TEST_PASSWORD}  ${TEST_VHOST}
    # Creation of a vhost takes some time
    sleep  ${TIMEOUT}
    Create Rabbitmq Connection  ${RABBITMQ_HOST}  ${RABBITMQ_PORT}  ${AMQP_PORT}  ${TEST_USER}  ${TEST_PASSWORD}  alias=rmq  vhost=${TEST_VHOST}
    Bulk Make Rabbitmq Queues  vhost=${TEST_VHOST}  queue=${TEST_QUEUE}  node_number=${0}  count=${ITERATIONS}
    ${backup_folder}  Make Rabbitmq Granular Backup  vhost=${TEST_VHOST}
    Wait Job Success  job_name=${backup_folder}
    Bulk Delete Queue  count=${ITERATIONS}  vhost=${TEST_VHOST}  queue=${TEST_QUEUE}

    ${restore_name}  Make Rabbitmq Granular Restore  vault_name=${backup_folder}  vhost=${TEST_VHOST}
    Wait Job Success  job_name=${restore_name}
    Evict Vault  vault_name=${backup_folder}
    Create Rabbitmq Connection  ${RABBITMQ_HOST}  ${RABBITMQ_PORT}  ${AMQP_PORT}  ${TEST_USER}  ${TEST_PASSWORD}  alias=rmq  vhost=${TEST_VHOST}
    ${exist}=  Bulk Queue Exist  count=${ITERATIONS}  vhost=${TEST_VHOST}  queue=${TEST_QUEUE}
    Should Be True  ${exist}
    Bulk Delete Queue  count=${ITERATIONS}  vhost=${TEST_VHOST}  queue=${TEST_QUEUE}
    Clean User
    Clean Vhost

