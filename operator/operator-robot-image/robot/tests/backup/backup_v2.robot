*** Settings ***

Resource          ../keywords.robot
Suite Setup       Preparation Rabbitmq Connnection

Library           S3BackupLibrary  url=%{S3_URL}
...               bucket=%{S3_BUCKET}
...               key_id=${S3_KEY_ID}
...               key_secret=${S3_KEY_SECRET}
...               ssl_verify=false

*** Variables ***
${S3_BUCKET}                 %{S3_BUCKET}
${BACKUP_STORAGE_PATH}       /opt/rabbitmq/backup-storage
${S3_ALIASES_SECRET_NAME}    %{S3_ALIASES_SECRET_NAME=rabbitmq-backup-daemon-s3-aliases}
${S3_DEFAULT_ALIAS_NAME}     %{S3_DEFAULT_ALIAS_NAME=default}

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

Ensure S3 Aliases Config Available
    ${secret_exists}=  Run Keyword And Return Status  Check Secret  ${S3_ALIASES_SECRET_NAME}  ${NAMESPACE}
    Pass Execution If  not ${secret_exists}  S3 aliases secret is absent, skip alias routing test
    ${secret}=  Check Secret  ${S3_ALIASES_SECRET_NAME}  ${NAMESPACE}
    ${has_alias_config}=  Evaluate  bool($secret.data) and 's3_aliases.json' in $secret.data and bool($secret.data['s3_aliases.json'])
    Pass Execution If  not ${has_alias_config}  S3 aliases config is empty, skip alias routing test

Get Default S3 Alias Config
    ${secret}=  Check Secret  ${S3_ALIASES_SECRET_NAME}  ${NAMESPACE}
    ${aliases_base64}=  Set Variable  ${secret.data['s3_aliases.json']}
    ${aliases_json}=  Evaluate  base64.b64decode($aliases_base64).decode("utf-8")  modules=base64
    ${aliases}=  Evaluate  json.loads('''${aliases_json}''')  json
    ${default_alias_name}=  Evaluate  next((name for name, cfg in $aliases.items() if cfg.get("default") is True), None)
    ${default_alias_name}=  Run Keyword If  "${default_alias_name}" == "${None}"  Set Variable  ${S3_DEFAULT_ALIAS_NAME}  ELSE  Set Variable  ${default_alias_name}
    ${default_alias}=  Evaluate  $aliases.get($default_alias_name)
    Should Not Be Equal  ${default_alias}  ${None}
    RETURN  ${default_alias}

Check Backup Exists In Default Alias Bucket
    [Arguments]  ${backup_id}  ${blob_path}
    ${default_alias}=  Get Default S3 Alias Config
    ${s3_url}=  Evaluate  $default_alias.get("s3Url") or $default_alias.get("storageServerUrl")
    ${s3_bucket}=  Evaluate  $default_alias.get("bucketName") or $default_alias.get("storageBucket")
    ${s3_key_id}=  Evaluate  $default_alias.get("accessKeyId") or $default_alias.get("storageUsername")
    ${s3_key_secret}=  Evaluate  $default_alias.get("accessKeySecret") or $S3_KEY_SECRET
    Should Not Be Empty  ${s3_url}
    Should Not Be Empty  ${s3_bucket}
    Should Not Be Empty  ${s3_key_id}
    Should Not Be Empty  ${s3_key_secret}
    Import Library  S3BackupLibrary  url=${s3_url}  bucket=${s3_bucket}  key_id=${s3_key_id}  key_secret=${s3_key_secret}  ssl_verify=false  WITH NAME  DefaultAliasS3
    ${backup_file_exist}=  DefaultAliasS3.Check Backup Exists  path=${blob_path}  backup_id=${backup_id}
    Should Be True  ${backup_file_exist}

Check Backup Does Not Exist In Base S3 Bucket
    [Arguments]  ${backup_id}  ${blob_path}
    ${backup_file_exist}=  Check Backup Exists  path=${blob_path}  backup_id=${backup_id}
    Should Not Be True  ${backup_file_exist}

*** Test Cases ***
Backup Uses Default S3 Alias Bucket
    [Tags]  backup  backup_v2  s3_storage  all
    Ensure S3 Aliases Config Available
    Create and check queue
    ${backup_folder}  Make Rabbitmq Full Backup
    Wait Job Success  job_name=${backup_folder}
    Check Backup Exists In Default Alias Bucket  ${backup_folder}  ${BACKUP_STORAGE_PATH}
    Check Backup Does Not Exist In Base S3 Bucket  ${backup_folder}  ${BACKUP_STORAGE_PATH}
    Evict Vault  vault_name=${backup_folder}
    sleep  ${TIMEOUT}
    Clear Data
