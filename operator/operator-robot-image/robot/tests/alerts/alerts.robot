*** Variables ***
${SOME_PODS_ARE_NOT_WORKING_ALERT}             SomePodsAreNotWorking
${ALERT_RETRY_TIME}                            5min
${ALERT_RETRY_INTERVAL}                        10s
${NO_METRICS_ALERT}                            NoMetrics
${RABBITMQ_PLUGIN_ENABLE}                      rabbitmq-plugins enable rabbitmq_prometheus
${RABBITMQ_PLUGIN_DISABLE}                     rabbitmq-plugins disable rabbitmq_prometheus

*** Settings ***
Library  MonitoringLibrary  host=%{PROMETHEUS_URL}
Resource  ../keywords.robot

*** Keywords ***
Check That Prometheus Alert Is Active
    [Arguments]  ${alert_name}
    ${status}=  Get Alert Status  ${alert_name}  ${NAMESPACE}
    Should Be True  '${status}' in ['pending', 'firing']

Check That Prometheus Alert Is Inactive
    [Arguments]  ${alert_name}
    ${status}=  Get Alert Status  ${alert_name}  ${NAMESPACE}
    Should Be Equal As Strings  ${status}    inactive

RabbitMQ Prometheus Plugin Switch
    [Arguments]  ${switch_position}
    FOR    ${item}    IN    @{pod_names}
        Execute Command In Pod  ${item}  ${NAMESPACE}  ${switch_position}
    END

Restore RabbitMQ App
    [Arguments]  ${pod_name}
    Run Keyword If  '${pod_name}' != '${EMPTY}'
    ...  Run Keyword And Ignore Error  Execute Command In Pod  ${pod_name}  ${NAMESPACE}  rabbitmqctl start_app

*** Test Cases ***
RabbitMQ Some Pods Are Not Working Alert
    [Tags]  all  alerts  some_pods_are_not_working_alert
    Set Test Variable  ${pod_name}  ${EMPTY}
    ${pod_name}=  Get First Rabbit Pod
    Set Test Variable  ${pod_name}
    # We need to wait because SomePodsAreNotWorking alert is firing during RabbitMQ StatefulSet upgrade
    Wait Until Keyword Succeeds    2 min    ${ALERT_RETRY_INTERVAL}
    ...  Check That Prometheus Alert Is Inactive  ${SOME_PODS_ARE_NOT_WORKING_ALERT}
    Execute Command In Pod  ${pod_name}  ${NAMESPACE}  rabbitmqctl stop_app
    Wait Until Keyword Succeeds    ${ALERT_RETRY_TIME}    ${ALERT_RETRY_INTERVAL}
    ...  Check That Prometheus Alert Is Active  ${SOME_PODS_ARE_NOT_WORKING_ALERT}
    Execute Command In Pod  ${pod_name}  ${NAMESPACE}  rabbitmqctl start_app
    Wait Until Keyword Succeeds    ${ALERT_RETRY_TIME}    ${ALERT_RETRY_INTERVAL}
    ...  Check That Prometheus Alert Is Inactive  ${SOME_PODS_ARE_NOT_WORKING_ALERT}
    [Teardown]  Restore RabbitMQ App  ${pod_name}

RabbitMQ No Metrics Alert
    [Tags]  all  alerts  no_metrics_alert
    Check That Prometheus Alert Is Inactive  ${NO_METRICS_ALERT}
    Get All Rabbit Pods
    RabbitMQ Prometheus Plugin Switch  ${RABBITMQ_PLUGIN_DISABLE}
    Wait Until Keyword Succeeds    ${ALERT_RETRY_TIME}    ${ALERT_RETRY_INTERVAL}
    ...  Check That Prometheus Alert Is Active  ${NO_METRICS_ALERT}
    RabbitMQ Prometheus Plugin Switch  ${RABBITMQ_PLUGIN_ENABLE}
    Wait Until Keyword Succeeds    ${ALERT_RETRY_TIME}    ${ALERT_RETRY_INTERVAL}
    ...  Check That Prometheus Alert Is Inactive  ${NO_METRICS_ALERT}
    [Teardown]  RabbitMQ Prometheus Plugin Switch  ${RABBITMQ_PLUGIN_ENABLE}
