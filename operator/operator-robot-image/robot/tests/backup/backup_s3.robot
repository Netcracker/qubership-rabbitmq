*** Settings ***

Resource          ../keywords.robot
Suite Setup       Preparation Rabbitmq Connnection

Library           S3BackupLibrary  url=%{S3_URL}
...               bucket=%{S3_BUCKET}
...               key_id=%{S3_KEY_ID}
...               key_secret=%{S3_KEY_SECRET}
...               ssl_verify=false

*** Variables ***
${S3_BUCKET}                 %{S3_BUCKET}
${BACKUP_STORAGE_PATH}       /opt/rabbitmq/backup-storage

*** Keywords ***
Clear Data
    Delete and check queue
    Clean User
    Clean Vhost

Preparation Rabbitmq Connnection
    ${alive}  Is Rabbit Alive
    Should Be True  ${alive}

    ${bucket_created}=  Check Bucket Exists  ${S3_BUCKET}
    Should Be True  ${bucket_created}
    Create Test User And Vhost  ${TEST_USER}  ${TEST_PASSWORD}  ${TEST_VHOST}

    Create Rabbitmq Connection  ${RABBITMQ_HOST}  ${RABBITMQ_PORT}  ${AMQP_PORT}  ${TEST_USER}  ${TEST_PASSWORD}  alias=rmq  vhost=${TEST_VHOST}
    # Creation of a vhost takes some time
    sleep  ${TIMEOUT}

*** Test Cases ***
Granular Backup And Restore On S3 Storage
    [Tags]  backup  granular_backup  granular_backup_s3  s3_storage  all

    Create and check queue
    ${backup_folder}  Make Rabbitmq Granular Backup  vhost=${TEST_VHOST}
    Wait Job Success  job_name=${backup_folder}
    Delete and check queue

    #Check backup created in S3
    ${backup_file_exist}=  Check Backup Exists    path=${BACKUP_STORAGE_PATH}/granular    backup_id=${backup_folder}
    Should Be True  ${backup_file_exist}
    ${restore_name}   Make Rabbitmq Granular Restore  vault_name=${backup_folder}  vhost=${TEST_VHOST}
    Wait Job Success  job_name=${restore_name}

    #Remove backup from S3
    Evict Vault  vault_name=${backup_folder}
    # evicting backup files takes some time
    sleep  ${TIMEOUT}
    ${backup_file_exist}=  Check Backup Exists    path=${BACKUP_STORAGE_PATH}/granular    backup_id=${backup_folder}
    Should Not Be True  ${backup_file_exist}
    ${exist}=  Queue Exist  ${TEST_VHOST}  ${TEST_QUEUE}
    Should Be True  ${exist}

    Clear Data

Full Backup And Restore On S3 Storage
    [Tags]  backup  full_backup  full_backup_s3  s3_storage  all

    ${alive}  Is Rabbit Alive
    Should Be True  ${alive}

    ${bucket_created}=  Check Bucket Exists  ${S3_BUCKET}
    Should Be True  ${bucket_created}
    Create Test User And Vhost  ${TEST_USER}  ${TEST_PASSWORD}  ${TEST_VHOST}

    # Creation of a vhost takes some time
    sleep  ${TIMEOUT}
    Create and check queue
    ${backup_folder}  Make Rabbitmq Full Backup
    Wait Job Success  job_name=${backup_folder}

    Clear Data

    #Check backup created in S3
    ${backup_file_exist}=  Check Backup Exists    path=${BACKUP_STORAGE_PATH}    backup_id=${backup_folder}
    ${restore_name}   Make Rabbitmq Full Restore  vault_name=${backup_folder}
    Wait Job Success  job_name=${restore_name}

    #Remove backup from S3
    Evict Vault  vault_name=${backup_folder}
    # evicting backup files takes some time
    sleep  ${TIMEOUT}
    ${backup_file_exist}=  Check Backup Exists    path=${BACKUP_STORAGE_PATH}    backup_id=${backup_folder}
    Should Not Be True  ${backup_file_exist}
    ${exist}=  Queue Exist  ${TEST_VHOST}  ${TEST_QUEUE}
    Should Be True  ${exist}

    Clear Data
