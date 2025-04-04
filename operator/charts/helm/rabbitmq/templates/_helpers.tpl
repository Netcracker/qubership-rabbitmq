{{/* vim: set filetype=mustache: */}}
{{/*
Expand the name of the chart.
*/}}
{{- define "helm-chart.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "helm-chart.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- $name := default .Chart.Name .Values.nameOverride -}}
{{- if contains $name .Release.Name -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "helm-chart.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Common labels
*/}}
{{- define "helm-chart.labels" -}}
helm.sh/chart: {{ include "helm-chart.chart" . }}
{{ include "helm-chart.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{/*
Selector labels
*/}}
{{- define "helm-chart.selectorLabels" -}}
app.kubernetes.io/name: {{ include "helm-chart.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{/*
Create the name of the service account to use
*/}}
{{- define "helm-chart.serviceAccountName" -}}
{{- if .Values.serviceAccount.create -}}
    {{ default (include "helm-chart.fullname" .) .Values.serviceAccount.name }}
{{- else -}}
    {{ default "default" .Values.serviceAccount.name }}
{{- end -}}
{{- end -}}

{{/*
Create the list of enabled RabbitMQ plugins
*/}}
{{- define "rabbitmq.enabledPlugins" -}}
{{- $plugins := append .Values.rabbitmq.enabledPlugins "rabbitmq_management" }}
{{- $plugins = append $plugins "rabbitmq_shovel_management" }}
{{- if .Values.rabbitmq.eventLogging }}
{{- $plugins = append $plugins "rabbitmq_event_exchange" }}
{{- end }}
{{- if not .Values.rabbitmq.hostpath_configuration }}
{{- $plugins = append $plugins "rabbitmq_peer_discovery_k8s" }}
{{- end }}
{{- if and (eq (include "monitoring.enabled" .) "true") (not (has "rabbitmq_prometheus" $plugins)) }}
{{- $plugins = append $plugins "rabbitmq_prometheus" }}
{{- end }}
{{- $plugins = append $plugins "rabbitmq_auth_backend_ldap" }}
{{- join "," $plugins }}
{{- end }}

{{/*
Create the RabbitMQ cluster configuration
*/}}
{{- define "rabbitmq.clusterConfiguration" -}}
{{- if .Values.rabbitmq.hostpath_configuration -}}
cluster_formation.peer_discovery_backend = rabbit_peer_discovery_classic_config
{{- range until (.Values.rabbitmq.replicas | int) }}
{{ printf "cluster_formation.classic_config.nodes.%d = rabbit@rmqlocal-%d-0" . . }}
{{- end }}
{{- else -}}
cluster_formation.peer_discovery_backend = rabbit_peer_discovery_k8s
cluster_formation.k8s.host = kubernetes.default.svc.cluster.local
cluster_formation.k8s.address_type = hostname
{{- end }}
cluster_partition_handling = autoheal
{{- end }}

{{/*
Create the RabbitMQ SSL configuration
*/}}
{{- define "rabbitmq.sslConfiguration" -}}
{{- if and .Values.global.tls.enabled .Values.rabbitmq.tls.enabled -}}
ssl_options.cacertfile = /tls/ca.crt
ssl_options.certfile   = /tls/tls.crt
ssl_options.keyfile    = /tls/tls.key
ssl_options.verify     = verify_peer
ssl_options.fail_if_no_peer_cert = false
listeners.ssl.default = 5671
management.ssl.port = 15671
management.ssl.cacertfile = /tls/ca.crt
management.ssl.certfile   = /tls/tls.crt
management.ssl.keyfile    = /tls/tls.key
{{ if not .Values.global.tls.allowNonencryptedAccess }}
listeners.tcp = none
{{- else }}
management.tcp.port = 15672
{{- end }}
{{- $suites := coalesce .Values.rabbitmq.tls.cipherSuites .Values.global.tls.cipherSuites }}
{{ range $i, $s := ($suites) }}
{{ printf "management.ssl.ciphers.%d = %s" (add $i 1) $s }}
{{ printf "ssl_options.ciphers.%d = %s" (add $i 1) $s }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create the list of advanced RabbitMQ configuration
*/}}
{{- define "rabbitmq.advancedConfig" -}}
{{- $configs := .Values.rabbitmq.customAdvancedProperties }}
{{- if .Values.rabbitmq.ipv6_enabled }}
{{- $configs = append $configs `{rabbitmq_management, [
        {listener, [
            {port, 15672},
            {ip, {0, 0, 0, 0, 0, 0, 0, 0}}
        ]}
    ]}`}}
{{- end }}
{{- if .Values.rabbitmq.ldap.enabled }}
{{- $ldapConfig := .Values.rabbitmq.ldap.advancedConfig }}
{{- $configs = append $configs $ldapConfig }}
{{- end }}
{{- join ",\n" $configs }}
{{- end }}

{{/*
Replace watermark in percent with float value
*/}}
{{- define "rabbitmq.cutWatermark" -}}
{{- $watermark := .Values.rabbitmq.custom_params.rabbitmq_vm_memory_high_watermark }}
{{- $watermark = trunc 2 $watermark }}
{{- printf " 0.%s" $watermark }}
{{- end }}

{{/*
Calculate RAM limit in megabytes or mebibytes
*/}}
{{- define "rabbitmq.memoryLimitMegaBytes" -}}
{{- $memory := .Values.rabbitmq.resources.limits.memory }}
{{- if contains "Gi" $memory }}
    {{- $memory = trimSuffix "Gi" $memory }}
    {{- if contains "." $memory }}
        {{- $memory = trunc -1 $memory }}
        {{- printf " %s00MiB" $memory }}
    {{- else }}
        {{- printf " %s000MiB" $memory }}
    {{- end }}
{{- else }}
    {{- if contains "G" $memory }}
        {{- $memory = trimSuffix "G" $memory }}
        {{- if contains "." $memory }}
            {{- $memory = trunc -1 $memory }}
            {{- printf " %s00MB" $memory }}
        {{- else }}
            {{- printf " %s000MB" $memory }}
        {{- end }}
    {{- else }}
        {{- printf " %sB" $memory }}
    {{- end }}
{{- end }}
{{- end }}

{{/*
Find a RabbitMQ service operator image in various places.
Image can be found from:
* SaaS/App deployer (or groovy.deploy.v3) from .Values.deployDescriptor "rabbitmq" "image"
* DP.Deployer from .Values.deployDescriptor.operator.image
* or from default values .Values.operatorImage
*/}}
{{- define "operator.image" -}}
  {{- printf "%s" .Values.operatorImage -}}
{{- end -}}

{{/*
Find a RabbitMQ disaster recovery service operator image in various places.
Image can be found from:
* SaaS/App deployer (or groovy.deploy.v3) from .Values.disasterRecoveryImage
* DP.Deployer from .Values.deployDescriptor.disasterRecoveryImage.image
* or from default values .Values.disasterRecovery.image
*/}}
{{- define "disasterRecovery.image" -}}
  {{- printf "%s" .Values.disasterRecovery.image -}}
{{- end -}}

{{/*
Find a RabbitMQ backup daemon image in various places.
*/}}
{{- define "backupDaemon.image" -}}
  {{- printf "%s" .Values.backupDaemon.image -}}
{{- end -}}

{{/*
Find a RabbitMQ image in various places.
*/}}
{{- define "rabbitmq.image" -}}
  {{- printf "%s" .Values.rabbitmq.dockerImage -}}
{{- end -}}

{{/*
Storage class from various places.
*/}}
{{- define "rabbitmq.storageclass" -}}
  {{- if and (ne (.Values.STORAGE_RWO_CLASS | toString) "<nil>") .Values.global.cloudIntegrationEnabled -}}
    {{- .Values.STORAGE_RWO_CLASS }}
  {{- else -}}
    {{- .Values.rabbitmq.resources.storageclass -}}
  {{- end -}}
{{- end -}}

{{/*
Enable Prometheus monitoring.
*/}}
{{- define "monitoring.enabled" -}}
  {{- if and (ne (.Values.MONITORING_ENABLED | toString) "<nil>") .Values.global.cloudIntegrationEnabled -}}
    {{- .Values.MONITORING_ENABLED }}
  {{- else -}}
    {{- .Values.rabbitmqPrometheusMonitoring -}}
  {{- end -}}
{{- end -}}

{{/*
RabbitMQ admin username.
*/}}
{{- define "rabbitmq.adminUsername" -}}
  {{- if and (ne (.Values.INFRA_RABBITMQ_ADMIN_USERNAME | toString) "<nil>") .Values.global.cloudIntegrationEnabled -}}
    {{- .Values.INFRA_RABBITMQ_ADMIN_USERNAME }}
  {{- else -}}
    {{- required "The rabbitmq.custom_params.rabbitmq_default_user should be specified" .Values.rabbitmq.custom_params.rabbitmq_default_user -}}
  {{- end -}}
{{- end -}}

{{/*
RabbitMQ admin password.
*/}}
{{- define "rabbitmq.adminPassword" -}}
  {{- if and (ne (.Values.INFRA_RABBITMQ_ADMIN_PASSWORD | toString) "<nil>") .Values.global.cloudIntegrationEnabled -}}
    {{- .Values.INFRA_RABBITMQ_ADMIN_PASSWORD }}
  {{- else -}}
    {{- required "The rabbitmq.custom_params.rabbitmq_default_password should be specified" .Values.rabbitmq.custom_params.rabbitmq_default_password -}}
  {{- end -}}
{{- end -}}

{{/*
Find a RabbitMQ tests image in various places.
*/}}
{{- define "tests.image" -}}
  {{- printf "%s" .Values.tests.dockerImage -}}
{{- end -}}

{{/*
Find a RabbitMQ telegraf image in various places.
*/}}
{{- define "telegraf.image" -}}
  {{- printf "%s" .Values.telegraf.dockerImage -}}
{{- end -}}

{{/*
Find a Deployment Status Provisioner image in various places.
*/}}
{{- define "deployment-status-provisioner.image" -}}
  {{- printf "%s" .Values.statusProvisioner.dockerImage -}}
{{- end -}}

{{/*
Find a kubectl image in various places.
*/}}
{{- define "kubectl.image" -}}
  {{- printf "%s" .Values.operator.restartScheduler.dockerImage -}}
{{- end -}}

{{/*
Calculates resources that should be monitored during deployment by Deployment Status Provisioner.
*/}}
{{- define "rabbitmq.monitoredResources" -}}
  {{- if and .Values.externalRabbitmq.enabled .Values.telegraf.install -}}
    {{- printf "Deployment rabbit-monitoring-external, " -}}
  {{- end -}}
  {{- if and .Values.externalRabbitmq.enabled .Values.backupDaemon.enabled }}
    {{- printf "Deployment rabbitmq-backup-daemon, " -}}
  {{- end -}}
  {{- if and .Values.externalRabbitmq.enabled .Values.tests.runTests .Values.tests.waitTestResultOnJob }}
    {{- printf "Deployment rabbitmq-integration-tests, " -}}
  {{- end -}}
{{- end -}}

{{- define "rabbitmq.globalPodSecurityContext" -}}
{{- if not .Values.global.disableRunAsNonRoot }}
runAsNonRoot: true
{{- end }}
seccompProfile:
  type: "RuntimeDefault"
{{- with .Values.global.securityContext }}
{{ toYaml . }}
{{- end -}}
{{- end -}}

{{- define "rabbitmq.globalContainerSecurityContext" -}}
allowPrivilegeEscalation: false
capabilities:
  drop: ["ALL"]
{{- end -}}

{{/*
Configure RabbitMQ service 'enableDisasterRecovery' property
*/}}
{{- define "rabbitmq.enableDisasterRecovery" -}}
  {{- if or (eq .Values.disasterRecovery.mode "active") (eq .Values.disasterRecovery.mode "standby") (eq .Values.disasterRecovery.mode "disable") -}}
    {{- printf "true" }}
  {{- else -}}
    {{- printf "false" }}
  {{- end -}}
{{- end -}}

{{- define "restart-scheduler-enabled" -}}
{{- if and .Values.operator.restartScheduler.enabled (eq (include "rabbitmq.enableDisasterRecovery" .) "true") }}
  {{- "true" -}}
{{- else }}
  {{- "false" -}}
{{- end -}}
{{- end -}}

{{/*
Configure RabbitMQ statefulset names in disaster recovery health check format.
*/}}
{{- define "rabbitmq.statefulsetNames" -}}
  {{- if .Values.rabbitmq.hostpath_configuration }}
    {{- $replicas := .Values.rabbitmq.replicas }}
    {{- $lst := list }}
    {{- range $i, $e := until ($replicas | int) }}
      {{- $lst = append $lst (printf "statefulset %s-%d" "rmqlocal" (add $i 0))  }}
    {{- end }}
    {{- join "," $lst }}
  {{- else -}}
    {{- printf "statefulset rmqlocal" }}
  {{- end -}}
{{- end -}}

{{/*
Provider used to generate SSL certificates
*/}}
{{- define "services.certProvider" -}}
  {{- default "helm" .Values.global.tls.generateCerts.certProvider -}}
{{- end -}}

{{/*
Whether RabbitMQ certificates are specified
*/}}
{{- define "rabbitmq.certificatesSpecified" -}}
  {{- $filled := false -}}
  {{- range $key, $value := .Values.rabbitmq.tls.certificates -}}
    {{- if $value -}}
        {{- $filled = true -}}
    {{- end -}}
  {{- end -}}
  {{- $filled -}}
{{ end }}

{{/*
RabbitMQ SSL secret name
*/}}
{{- define "rabbitmq.tlsSecretName" -}}
  {{- if .Values.externalRabbitmq.enabled -}}
    {{- .Values.externalRabbitmq.sslSecretName -}}
  {{- else -}}
    {{- if and .Values.global.tls.enabled .Values.rabbitmq.tls.enabled -}}
      {{- if and (or .Values.global.tls.generateCerts.enabled (eq (include "rabbitmq.certificatesSpecified" .) "true")) (not .Values.rabbitmq.tls.secretName) -}}
        {{- printf "rabbitmq-tls-secret" -}}
      {{- else -}}
        {{- required "The TLS secret name should be specified in the 'rabbitmq.tls.secretName' parameter when the service is deployed with rabbitmq and TLS enabled, but without certificates generation." .Values.rabbitmq.tls.secretName -}}
      {{- end -}}
    {{- else -}}
       {{/*
        The empty string is needed for correct prometheus rule configuration in `tls_static_metrics.yaml`
       */}}
      {{- "" -}}
    {{- end -}}
  {{- end -}}
{{- end -}}

{{/*
Whether RabbitMQ SSL enabled
*/}}
{{- define "rabbitmq.enableTls" -}}
  {{- if .Values.externalRabbitmq.enabled -}}
    {{- .Values.externalRabbitmq.enableSsl -}}
  {{- else -}}
    {{- and .Values.global.tls.enabled .Values.rabbitmq.tls.enabled -}}
  {{- end -}}
{{- end -}}

{{/*
Protocol for RabbitMQ
*/}}
{{- define "rabbitmq.protocol" -}}
{{- ternary "https" "http" (eq (include "rabbitmq.enableTls" .) "true")  -}}
{{- end -}}

{{/*
Port for RabbitMQ
*/}}
{{- define "rabbitmq.port" -}}
{{- ternary "15671" "15672" (eq (include "rabbitmq.enableTls" .) "true")  -}}
{{- end -}}

{{/*
Whether ingress for RabbitMQ enabled
*/}}
{{- define "rabbitmq.ingressEnabled" -}}
  {{- if and (ne (.Values.PRODUCTION_MODE | toString) "<nil>") .Values.global.cloudIntegrationEnabled}}
    {{- (eq .Values.PRODUCTION_MODE false) }}
  {{- else -}}
    {{- .Values.rabbitmq.ingress.enabled }}
  {{- end -}}
{{- end -}}

{{/*
Ingress host for RabbitMQ
*/}}
{{- define "rabbitmq.ingressHost" -}}
  {{- if .Values.rabbitmq.ingress.host }}
    {{- .Values.rabbitmq.ingress.host }}
  {{- else -}}
    {{- if and (ne (.Values.SERVER_HOSTNAME | toString) "<nil>") .Values.global.cloudIntegrationEnabled }}
      {{- printf "rabbitmq-%s.%s" .Release.Namespace .Values.SERVER_HOSTNAME }}
    {{- end -}}
  {{- end -}}
{{- end -}}

{{/*
DNS names used to generate SSL certificate with "Subject Alternative Name" field
*/}}
{{- define "rabbitmq.certDnsNames" -}}
  {{- $rabbitmqName := "rabbitmq" -}}
  {{- $dnsNames := list "localhost" $rabbitmqName (printf "%s.%s" $rabbitmqName .Release.Namespace) (printf "%s.%s.svc.cluster.local" $rabbitmqName .Release.Namespace) (printf "%s.%s.svc" $rabbitmqName .Release.Namespace) -}}
  {{- $nodes := .Values.rabbitmq.replicas -}}
  {{- $rabbitmqNamespace := .Release.Namespace -}}
  {{- range $i, $e := until ($nodes | int) -}}
    {{- $dnsNames = append $dnsNames (printf "%s-%d.rmqlocal.%s.svc.cluster.local" $rabbitmqName $i $rabbitmqNamespace) -}}
  {{- end -}}
  {{ if (eq (include "rabbitmq.ingressEnabled" .) "true") }}
  {{- $dnsNames = append $dnsNames (include "rabbitmq.ingressHost" .) -}}
  {{- end -}}
  {{- $dnsNames = concat $dnsNames .Values.rabbitmq.tls.subjectAlternativeName.additionalDnsNames -}}
  {{- $dnsNames | toYaml -}}
{{- end -}}

{{/*
IP addresses used to generate SSL certificate with "Subject Alternative Name" field
*/}}
{{- define "rabbitmq.certIpAddresses" -}}
  {{- $ipAddresses := list "127.0.0.1" -}}
  {{- $ipAddresses = concat $ipAddresses .Values.rabbitmq.tls.subjectAlternativeName.additionalIpAddresses -}}
  {{- $ipAddresses | toYaml -}}
{{- end -}}

{{/*
Generate certificates for RabbitMQ
*/}}
{{- define "rabbitmq.generateCerts" -}}
  {{- $dnsNames := include "rabbitmq.certDnsNames" . | fromYamlArray -}}
  {{- $ipAddresses := include "rabbitmq.certIpAddresses" . | fromYamlArray -}}
  {{- $duration := default 365 .Values.global.tls.generateCerts.durationDays | int -}}
  {{- $ca := genCA "rabbitmq-ca" $duration -}}
  {{- $rabbitmqName := "rabbitmq" -}}
  {{- $cert := genSignedCert $rabbitmqName $ipAddresses $dnsNames $duration $ca -}}
tls.crt: {{ $cert.Cert | b64enc }}
tls.key: {{ $cert.Key | b64enc }}
ca.crt: {{ $ca.Cert | b64enc }}
{{- end -}}

{{/*
DRD Port
*/}}
{{- define "disasterRecovery.port" -}}
  {{- if eq (include "disasterRecovery.enableTls" .) "true" -}}
    {{- "8443" -}}
  {{- else -}}
    {{- "8080" -}}
  {{- end -}}
{{- end -}}

{{/*
Whether DRD certificates are Specified
*/}}
{{- define "disasterRecovery.certificatesSpecified" -}}
  {{- $filled := false -}}
  {{- range $key, $value := .Values.disasterRecovery.tls.certificates -}}
    {{- if $value -}}
        {{- $filled = true -}}
    {{- end -}}
  {{- end -}}
  {{- $filled -}}
{{- end -}}

{{/*
DRD SSL secret name
*/}}
{{- define "disasterRecovery.tlsSecretName" -}}
  {{- if (eq (include "disasterRecovery.enableTls" .) "true") -}}
    {{- if and (or .Values.global.tls.generateCerts.enabled (eq (include "disasterRecovery.certificatesSpecified" .) "true")) (not .Values.disasterRecovery.tls.secretName) -}}
      {{- printf "rabbitmq-drd-tls-secret" -}}
    {{- else -}}
      {{- required "The TLS secret name should be specified in the 'disasterRecovery.tls.secretName' parameter when the service is deployed with disasterRecovery and TLS enabled, but without certificates generation." .Values.disasterRecovery.tls.secretName -}}
    {{- end -}}
  {{- else -}}
     {{/*
        The empty string is needed for correct prometheus rule configuration in `tls_static_metrics.yaml`
     */}}
    {{- "" -}}
  {{- end -}}
{{- end -}}

{{/*
DRD SSL ciphers suites
*/}}
{{- define "disasterRecovery.cipherSuites" -}}
{{ join "," (coalesce .Values.disasterRecovery.tls.cipherSuites .Values.global.tls.cipherSuites) }}
{{- end -}}

{{/*
DNS names used to generate SSL certificate with "Subject Alternative Name" field for DRD
*/}}
{{- define "disasterRecovery.certDnsNames" -}}
  {{- $drdNamespace := .Release.Namespace -}}
  {{- $dnsNames := list "localhost" (printf "rabbitmq-disaster-recovery.%s" $drdNamespace) (printf "rabbitmq-disaster-recovery.%s.svc.cluster.local" $drdNamespace) -}}
  {{- $dnsNames = concat $dnsNames .Values.disasterRecovery.tls.subjectAlternativeName.additionalDnsNames -}}
  {{- $dnsNames | toYaml -}}
{{- end -}}

{{/*
IP addresses used to generate SSL certificate with "Subject Alternative Name" field for DRD
*/}}
{{- define "disasterRecovery.certIpAddresses" -}}
  {{- $ipAddresses := list "127.0.0.1" -}}
  {{- $ipAddresses = concat $ipAddresses .Values.disasterRecovery.tls.subjectAlternativeName.additionalIpAddresses -}}
  {{- $ipAddresses | toYaml -}}
{{- end -}}

{{/*
Generate certificates for DRD
*/}}
{{- define "disasterRecovery.generateCerts" -}}
  {{- $dnsNames := include "disasterRecovery.certDnsNames" . | fromYamlArray -}}
  {{- $ipAddresses := include "disasterRecovery.certIpAddresses" . | fromYamlArray -}}
  {{- $duration := default 365 .Values.global.tls.generateCerts.durationDays | int -}}
  {{- $ca := genCA "rabbitmq-drd-ca" $duration -}}
  {{- $drdName := "drd" -}}
  {{- $cert := genSignedCert $drdName $ipAddresses $dnsNames $duration $ca -}}
tls.crt: {{ $cert.Cert | b64enc }}
tls.key: {{ $cert.Key | b64enc }}
ca.crt: {{ $ca.Cert | b64enc }}
{{- end -}}

{{/*
Protocol for DRD
*/}}
{{- define "disasterRecovery.protocol" -}}
{{- if eq (include "disasterRecovery.enableTls" .) "true" -}}
  {{- "https" -}}
{{- else -}}
  {{- "http" -}}
{{- end -}}
{{- end -}}

{{/*
Backup Daemon Port
*/}}
{{- define "backupDaemon.port" -}}
  {{- if (eq (include "backupDaemon.enableTls" .) "true") -}}
    {{- "8443" -}}
  {{- else -}}
    {{- "8080" -}}
  {{- end -}}
{{- end -}}

{{/*
Whether Backup Daemon certificates are Specified
*/}}
{{- define "backupDaemon.certificatesSpecified" -}}
  {{- $filled := false -}}
  {{- range $key, $value := .Values.backupDaemon.tls.certificates -}}
    {{- if $value -}}
        {{- $filled = true -}}
    {{- end -}}
  {{- end -}}
  {{- $filled -}}
{{ end }}

{{/*
Backup Daemon SSL secret name
*/}}
{{- define "backupDaemon.tlsSecretName" -}}
  {{- if (eq (include "backupDaemon.enableTls" .) "true") -}}
    {{- if and (or .Values.global.tls.generateCerts.enabled (eq (include "backupDaemon.certificatesSpecified" .) "true")) (not .Values.backupDaemon.tls.secretName) -}}
      {{- printf "rabbitmq-backup-daemon-tls-secret" -}}
    {{- else -}}
      {{- required "The TLS secret name should be specified in the 'backupDaemon.tls.secretName' parameter when the service is deployed with backupDaemon and TLS enabled, but without certificates generation." .Values.backupDaemon.tls.secretName -}}
    {{- end -}}
  {{- else -}}
     {{/*
        The empty string is needed for correct prometheus rule configuration in `tls_static_metrics.yaml`
     */}}
    {{- "" -}}
  {{- end -}}
{{- end -}}

{{/*
Backup Daemon SSL secret name
*/}}
{{- define "backupDaemon.s3.tlsSecretName" -}}
  {{- if .Values.backupDaemon.s3.sslCert -}}
    {{- if .Values.backupDaemon.s3.sslSecretName -}}
      {{- .Values.backupDaemon.s3.sslSecretName -}}
    {{- else -}}
      {{- printf "rabbitmq-backup-daemon-s3-tls-secret" -}}
    {{- end -}}
  {{- else -}}
    {{- if .Values.backupDaemon.s3.sslSecretName -}}
      {{- .Values.backupDaemon.s3.sslSecretName -}}
    {{- else -}}
      {{- printf "" -}}
    {{- end -}}
  {{- end -}}
{{- end -}}

{{/*
DNS names used to generate SSL certificate with "Subject Alternative Name" field for Backup Daemon
*/}}
{{- define "backupDaemon.certDnsNames" -}}
  {{- $backupDaemonNamespace := .Release.Namespace -}}
  {{- $dnsNames := list "localhost" "rabbitmq-backup-daemon" (printf "rabbitmq-backup-daemon.%s" $backupDaemonNamespace) (printf "rabbitmq-backup-daemon.%s.svc.cluster.local" $backupDaemonNamespace) -}}
  {{- $dnsNames = concat $dnsNames .Values.backupDaemon.tls.subjectAlternativeName.additionalDnsNames -}}
  {{- $dnsNames | toYaml -}}
{{- end -}}

{{/*
IP addresses used to generate SSL certificate with "Subject Alternative Name" field for Backup Daemon
*/}}
{{- define "backupDaemon.certIpAddresses" -}}
  {{- $ipAddresses := list "127.0.0.1" -}}
  {{- $ipAddresses = concat $ipAddresses .Values.backupDaemon.tls.subjectAlternativeName.additionalIpAddresses -}}
  {{- $ipAddresses | toYaml -}}
{{- end -}}

{{/*
Generate certificates for Backup Daemon
*/}}
{{- define "backupDaemon.generateCerts" -}}
  {{- $dnsNames := include "backupDaemon.certDnsNames" . | fromYamlArray -}}
  {{- $ipAddresses := include "backupDaemon.certIpAddresses" . | fromYamlArray -}}
  {{- $duration := default 365 .Values.global.tls.generateCerts.durationDays | int -}}
  {{- $ca := genCA "rabbitmq-backup-daemon-ca" $duration -}}
  {{- $backupDaemonName := "backupDaemon" -}}
  {{- $cert := genSignedCert $backupDaemonName $ipAddresses $dnsNames $duration $ca -}}
tls.crt: {{ $cert.Cert | b64enc }}
tls.key: {{ $cert.Key | b64enc }}
ca.crt: {{ $ca.Cert | b64enc }}
{{- end -}}

{{/*
Whether BackupDaemon TLS enabled
*/}}
{{- define "backupDaemon.enableTls" -}}
  {{- and .Values.global.tls.enabled .Values.backupDaemon.tls.enabled -}}
{{- end -}}

{{/*
BackupDaemon S3 endpoint
*/}}
{{- define "backupDaemon.s3Endpoint" -}}
  {{- if and (ne (.Values.S3_ENDPOINT | toString) "<nil>") .Values.global.cloudIntegrationEnabled -}}
    {{- .Values.S3_ENDPOINT }}
  {{- else -}}
    {{- .Values.backupDaemon.s3.url -}}
  {{- end -}}
{{- end -}}

{{/*
BackupDaemon S3 accessKey
*/}}
{{- define "backupDaemon.s3AccessKey" -}}
  {{- if and (ne (.Values.S3_ACCESSKEY | toString) "<nil>") .Values.global.cloudIntegrationEnabled -}}
    {{- .Values.S3_ACCESSKEY }}
  {{- else -}}
    {{- .Values.backupDaemon.s3.keyId  -}}
  {{- end -}}
{{- end -}}

{{/*
BackupDaemon S3 accessSecret
*/}}
{{- define "backupDaemon.s3AccessSecret" -}}
  {{- if and (ne (.Values.S3_SECRETKEY | toString) "<nil>") .Values.global.cloudIntegrationEnabled -}}
    {{- .Values.S3_SECRETKEY }}
  {{- else -}}
    {{- .Values.backupDaemon.s3.keySecret  -}}
  {{- end -}}
{{- end -}}

{{/*
Whether Disaster Recovery TLS enabled
*/}}
{{- define "disasterRecovery.enableTls" -}}
  {{- and .Values.global.tls.enabled .Values.disasterRecovery.tls.enabled -}}
{{- end -}}

{{/*
TLS Static Metric secret template
Arguments:
Dictionary with:
* "namespace" is a namespace of application
* "application" is name of application
* "service" is a name of service
* "enableTls" is tls enabled for service
* "secret" is a name of tls secret for service
* "certProvider" is a type of tls certificates provider
* "certificate" is a name of CertManager's Certificate resource for service
Usage example:
{{template "global.tlsStaticMetric" (dict "namespace" .Release.Namespace "application" .Chart.Name "service" .global.name "enableTls" (include "global.enableTls" .) "secret" (include "global.tlsSecretName" .) "certProvider" (include "services.certProvider" .) "certificate" (printf "%s-tls-certificate" (include "global.name")) }}
*/}}
{{- define "global.tlsStaticMetric" -}}
- expr: {{ ternary "1" "0" (eq .enableTls "true") }}
  labels:
    namespace: "{{ .namespace }}"
    application: "{{ .application }}"
    service: "{{ .service }}"
    {{ if eq .enableTls "true" }}
    secret: "{{ .secret }}"
    {{ if eq .certProvider "cert-manager" }}
    certificate: "{{ .certificate }}"
    {{ end }}
    {{ end }}
  record: service:tls_status:info
{{- end -}}

{{/*
Timeout for integration tests
*/}}
{{- define "tests.timeout" -}}
  {{ .Values.tests.timeout | default 1800 }}
{{- end -}}

{{ define "find_image" }}
  {{- $root := index . 0 -}}
  {{- $service_name := index . 1 -}}
  {{- if index $root.Values.deployDescriptor $service_name }}
  {{- index $root.Values.deployDescriptor $service_name "image" }}
  {{- else }}
  {{- "not_found" }}
  {{- end }}
{{- end }}

{{- define "rabbitmq.monitoredImages" -}}
    {{- printf "deployment rabbitmq-operator rabbitmq-operator %s, " (include "find_image" (list . "rabbitmq")) -}}
  {{- if .Values.backupDaemon.enabled -}}
    {{- if index .Values "backupDaemonImage" -}}
      {{- printf "deployment rabbitmq-backup-daemon rabbitmq-backup-daemon %s, " (index .Values "backupDaemonImage") -}}
    {{- else -}}
      {{- printf "deployment rabbitmq-backup-daemon rabbitmq-backup-daemon not_found, " -}}
    {{- end -}}
  {{- end -}}
  {{- if .Values.rabbitmq.replicas -}}
    {{- if .Values.rabbitmq.hostpath_configuration -}}
        {{- printf "statefulset rmqlocal-0 rmqlocal-0 %s, " (include "find_image" (list . "RabbitMQ")) -}}
    {{- else -}}
        {{- printf "statefulset rmqlocal rmqlocal %s, " (include "find_image" (list . "RabbitMQ")) -}}
    {{- end -}}
  {{- end -}}
  {{- if .Values.tests.runTests -}}
    {{- if index .Values "testsImage" -}}
      {{- printf "deployment rabbitmq-integration-tests rabbitmq-integration-tests %s, " (index .Values "testsImage") -}}
    {{- else -}}
      {{- printf "deployment rabbitmq-integration-tests rabbitmq-integration-tests not_found, " -}}
    {{- end -}}
  {{- end -}}
{{- end -}}

{{/*
The most common RabbitMQ resources labels
*/}}
{{- define "rabbitmq.coreLabels" -}}
app.kubernetes.io/version: '{{ .Values.ARTIFACT_DESCRIPTOR_VERSION | trunc 63 | trimAll "-_." }}'
app.kubernetes.io/part-of: '{{ .Values.PART_OF }}'
{{- end -}}

{{/*
Core RabbitMQ resources labels with backend component label
*/}}
{{- define "rabbitmq.defaultLabels" -}}
{{ include "rabbitmq.coreLabels" . }}
app.kubernetes.io/component: 'backend'
{{- end -}}

{{- define "backupDaemon.persistentVolumeDefined" -}}
  {{- if eq (.Values.backupDaemon.persistentVolume | toString) "<nil>" -}}
    {{- "false" }}
  {{- else -}}
    {{- and (ne .Values.backupDaemon.persistentVolume "") (ne .Values.backupDaemon.persistentVolume "null") -}}
  {{- end -}}
{{- end -}}

{{- define "backupDaemon.storageClassDefined" -}}
  {{- if eq (.Values.backupDaemon.storageClass | toString) "<nil>" -}}
    {{- "false" }}
  {{- else -}}
    {{- and (ne .Values.backupDaemon.storageClass "") (ne .Values.backupDaemon.storageClass "null") -}}
  {{- end -}}
{{- end -}}

{{/*
Service Account for Site Manager depending on smSecureAuth
*/}}
{{- define "disasterRecovery.siteManagerServiceAccount" -}}
  {{- if .Values.disasterRecovery.httpAuth.smServiceAccountName -}}
    {{- .Values.disasterRecovery.httpAuth.smServiceAccountName -}}
  {{- else -}}
    {{- if .Values.disasterRecovery.httpAuth.smSecureAuth -}}
      {{- "site-manager-sa" -}}
    {{- else -}}
      {{- "sm-auth-sa" -}}
    {{- end -}}
  {{- end -}}
{{- end -}}