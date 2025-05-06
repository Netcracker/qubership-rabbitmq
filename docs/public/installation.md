The RabbitMQ-operator deployment includes a RabbitMQ operator and RabbitMQ of the specified configuration.
It can be deployed manually through helm in OpenShift or Kubernetes.

For this deployment, only the storage class and local PV configurations are supported.
Overall, the RabbitMQ configuration is similar to the RabbitMQ deployed with an OpenShift deployer, except that the OpenShift route is not created when deploying with the operator.
<!-- #GFCFilterMarkerStart# -->
[[_TOC_]]
<!-- #GFCFilterMarkerEnd# -->
# Prerequisites

## Common

Before you start the installation and configuration of a RabbitMQ cluster, ensure the following requirements are met:

* Kubernetes 1.21+ or OpenShift 4.10+
* `kubectl` 1.21+ or `oc` 4.10+ CLI
* Helm 3.0+
* All required CRDs are installed

### Custom Resource Definitions

The following Custom Resource Definitions should be installed to the cloud before the installation of RabbitMQ:

* `RabbitMQService` - When you deploy with restricted rights or the CRDs' creation is disabled by the Deployer job. For more information, see [Automatic CRD Upgrade](#automatic-crd-upgrade).
* `GrafanaDashboard`, `PrometheusRule`, and `ServiceMonitor` - They should be installed when you deploy RabbitMQ monitoring with `rabbitmqPrometheusMonitoring=true`.
  You need to install the Monitoring Operator service before the RabbitMQ installation.

**Important**: To create CRDs, you must have cloud rights for `CustomResourceDefinitions`. If the deployment user does
not have the necessary rights, you need to perform the steps described in
the [Deployment Permissions](#deployment-permissions) section before the installation.

**Note**: If you deploy RabbitMQ Service to Kubernetes version less than 1.16, you have to manually install [CRD](/docs/sources/crds/oc311crd.yaml) and disable automatic CRD creation by Helm in the following
way:

* Specify `--skip-crds` in the `ADDITIONAL_OPTIONS` parameter of the DP Deployer job.
* Specify `DISABLE_CRD=true;` in the `CUSTOM_PARAMS` parameter of the Groovy Deployer job.

### Deployment Permissions

To avoid using `cluster-wide` rights during the deployment, the following conditions are required:

* The cloud administrator creates the namespace/project in advance.
* The following grants should be provided for the `Role` of the deployment user:

    <details>
    <summary>Click to expand YAML</summary>

   ```yaml
  apiVersion: rbac.authorization.k8s.io/v1
  kind: Role
  metadata:
    namespace: rabbitmq-namespace
    name: deploy-user-role
  rules:
    - apiGroups:
        - qubership.org
      resources:
        - "*"
      verbs:
        - create
        - get
        - list
        - patch
        - update
        - watch
        - delete
    - apiGroups:
        - ""
      resources:
        - pods
        - services
        - endpoints
        - persistentvolumeclaims
        - configmaps
        - secrets
        - pods/exec
        - pods/portforward
        - pods/attach
        - serviceaccounts
      verbs:
        - create
        - get
        - list
        - patch
        - update
        - watch
        - delete
    - apiGroups:
        - apps
      resources:
        - deployments
        - deployments/scale
        - deployments/status
      verbs:
        - create
        - get
        - list
        - patch
        - update
        - watch
        - delete
        - deletecollection
    - apiGroups:
        - batch
      resources:
        - jobs
        - cronjobs
      verbs:
        - create
        - get
        - list
        - patch
        - update
        - watch
        - delete
    - apiGroups:
        - ""
      resources:
        - events
      verbs:
        - create
    - apiGroups:
        - apps
      resources:
        - statefulsets
      verbs:
        - create
        - delete
        - get
        - list
        - patch
        - update
    - apiGroups:
        - networking.k8s.io
      resources:
        - ingresses
      verbs:
        - create
        - delete
        - get
        - list
        - patch
        - update
    - apiGroups:
        - rbac.authorization.k8s.io
      resources:
        - roles
        - rolebindings
      verbs:
        - create
        - delete
        - get
        - list
        - patch
        - update
    - apiGroups:
        - integreatly.org
      resources:
        - grafanadashboards
      verbs:
        - create
        - delete
        - get
        - list
        - patch
        - update
    - apiGroups:
        - monitoring.coreos.com
      resources:
        - servicemonitors
        - prometheusrules
      verbs:
        - create
        - delete
        - get
        - list
        - patch
        - update
    - apiGroups:
        - cert-manager.io
      resources:
        - certificates
      verbs:
        - create
        - get
        - patch
    ```

    </details>

The following rules require `cluster-wide` permissions. If it is not possible to provide them to the deployment user, you have to apply the resources manually.

* If RabbitMQ is installed in the disaster recovery mode and authentication on the disaster recovery server is enabled, cluster role binding for the `system:auth-delegator` role must be created.

  <details>
  <summary>Click to expand YAML</summary>

  ```yaml
  kind: ClusterRoleBinding
  apiVersion: rbac.authorization.k8s.io/v1
  metadata:
    name: token-review-crb-NAMESPACE
  subjects:
    - kind: ServiceAccount
      name: rabbitmq-operator
      namespace: NAMESPACE
  roleRef:
    apiGroup: rbac.authorization.k8s.io
    kind: ClusterRole
    name: system:auth-delegator
  ```

  </details>

* To avoid applying manual CRD, the following grants should be provided for `ClusterRole` of the deployment user:

  ```yaml
  rules:
    - apiGroups: ["apiextensions.k8s.io"]
      resources: ["customresourcedefinitions"]
      verbs: ["get", "create", "patch"]
  ```

* Custom resource definition `RabbitMQService` should be created/applied before the installation if the corresponding
  rights cannot be provided to the deployment user.
  <!-- #GFCFilterMarkerStart# -->
  The CRD for this version is stored in [crd.yaml](../../operator/charts/helm/rabbitmq/crds/crd.yaml) and can be
  applied with the following command:

  ```sh
  kubectl replace -f crd.yaml
  ```
  <!-- #GFCFilterMarkerEnd# -->

* For integration with NC Monitoring, ensure that NC Monitoring is installed in the cluster and the cluster has monitoring entities defined CRDs for
  ServiceMonitor, PrometheusRule, and GrafanaDashboard.
  In this case, the rules mentioned earlier grant permissions for the monitoring entities. However, permissions for monitoring entities can be added separately later if required.
  For example:

  <details>
  <summary>Click to expand YAML</summary>

  ```yaml
  apiVersion: rbac.authorization.k8s.io/v1
  kind: Role
  metadata:
    name: prometheus-monitored
  rules:
  - apiGroups:
    - monitoring.coreos.com
    resources:
    - servicemonitors
    - prometheusrules
    - podmonitors
    verbs:
    - create
    - get
    - list
    - patch
    - update
    - watch
    - delete
  - apiGroups:
    - integreatly.org
    resources:
    - grafanadashboards
    verbs:
    - create
    - get
    - list
    - patch
    - update
    - watch
    - delete
  ```

  ```yaml
  apiVersion: rbac.authorization.k8s.io/v1
  kind: RoleBinding
  metadata:
      name: prometheus-monitored
      namespace: rabbitmq-namespace
  roleRef:
      apiGroup: rbac.authorization.k8s.io
      kind: Role
      name: prometheus-monitored
  subjects:
  - kind: User
    name: deploy-user
  ```

  </details>

## Kubernetes

* It is required to upgrade the component before upgrading Kubernetes. Follow the information in the tags regarding Kubernetes
  certified versions.

## OpenShift

* It is required to upgrade the component before upgrading OpenShift. Follow the information in the tags regarding OpenShift
  certified versions.

* For successful deployment on storage, it must be ensured that the PODs have full permissions to the storage.

  RabbitMQ can be installed over dynamically provisioned or local PVs. For local PVs that are accessible only from specific nodes, all PVs must have the node label.
  If you are using host bound PV configuration in cloud with restricted SCC, the PV folder should have an owner with a certain UID.

  ```sh
  chown -R 5000.5000 /var/lib/origin/openshift.local.volumes/<PV-NAME>
  ```

  You should also pre-create the project and annotate it with the same UID. For example, with the following annotation:

  ```text
   openshift.io/sa.scc.uid-range: 5000/5000
  ```

  Also, it is necessary to change the SELinux security context for the PV folder:

  ```sh
  chcon -R unconfined_u:object_r:container_file_t:s0 /var/lib/origin/openshift.local.volumes/<PV-NAME>
  ```

## Google Cloud

The `Google Storage` bucket is created if a backup is needed.

## AWS

The `AWS S3` bucket is created if a backup is needed.

# Best Practices and Recommendations

## HWE

The provided values do not guarantee that these values are correct for all cases. It is a general recommendation.
Resources should be calculated and estimated for each project case with test load on the SVT stand, especially the HDD size.

### Small

Recommended for development purposes, PoC, and demos.

| Module                 | CPU   | RAM, Gi | Storage, Gb |
|------------------------|-------|---------|-------------|
| RabbitMQ (x3)          | 1     | 1       | 10          |
| RabbitMQ Telegraf      | 0.1   | 0.2     | 0           |
| RabbitMQ Backup Daemon | 0.1   | 0.2     | 1           |
| RabbitMQ Operator      | 0.1   | 0.2     | 0           |
| **Total (Rounded)**    | **4** | **4**   | **31**      |

<details>
<summary>Click to expand YAML</summary>

```yaml
operator:
  resources:
    requests:
      cpu: 50m
      memory: 128Mi
    limits:
      cpu: 100m
      memory: 256Mi
rabbitmq:
  resources:
    requests:
      cpu: 300m
      memory: 1Gi
    limits:
      cpu: '1'
      memory: 1Gi
telegraf:
  resources:
    requests:
      cpu: 50m
      memory: 128Mi
    limits:
      cpu: 100m
      memory: 256Mi
backupDaemon:
  resources:
    requests:
      cpu: 50m
      memory: 128Mi
    limits:
      cpu: 100m
      memory: 256Mi
```

</details>

### Medium

Recommended for deployments with average load.

| Module                 | CPU   | RAM, Gi | Storage, Gb |
|------------------------|-------|---------|-------------|
| RabbitMQ (x3)          | 2     | 4       | 50          |
| RabbitMQ Telegraf      | 0.2   | 0.2     | 0           |
| RabbitMQ Backup Daemon | 0.1   | 0.2     | 1           |
| RabbitMQ Operator      | 0.1   | 0.2     | 0           |
| **Total (Rounded)**    | **7** | **13**  | **151**     |

<details>
<summary>Click to expand YAML</summary>

```yaml
operator:
  resources:
    requests:
      cpu: 50m
      memory: 128Mi
    limits:
      cpu: 100m
      memory: 256Mi
rabbitmq:
  environmentVariables:
    - RABBITMQ_DISTRIBUTION_BUFFER_SIZE=256000
  resources:
    requests:
      cpu: 300m
      memory: 2Gi
    limits:
      cpu: 2
      memory: 4Gi
telegraf:
  resources:
    requests:
      cpu: 50m
      memory: 128Mi
    limits:
      cpu: 200m
      memory: 256Mi
backupDaemon:
  resources:
    requests:
      cpu: 50m
      memory: 128Mi
    limits:
      cpu: 100m
      memory: 256Mi
```

</details>

### Large

Recommended for deployments with high workload and large amount of data.

| Module                 | CPU    | RAM, Gi | Storage, Gb |
|------------------------|--------|---------|-------------|
| RabbitMQ (x3)          | 4      | 16      | 100         |
| RabbitMQ Telegraf      | 0.2    | 0.2     | 0           |
| RabbitMQ Backup Daemon | 0.1    | 0.2     | 1           |
| RabbitMQ Operator      | 0.1    | 0.2     | 0           |
| **Total (Rounded)**    | **13** | **49**  | **301**     |

<details>
<summary>Click to expand YAML</summary>

```yaml
operator:
  resources:
    requests:
      cpu: 50m
      memory: 128Mi
    limits:
      cpu: 100m
      memory: 256Mi
rabbitmq:
  environmentVariables:
    - RABBITMQ_DISTRIBUTION_BUFFER_SIZE=384000
  resources:
    requests:
      cpu: 500m
      memory: 4Gi
    limits:
      cpu: 4
      memory: 16Gi
telegraf:
  resources:
    requests:
      cpu: 50m
      memory: 128Mi
    limits:
      cpu: 200m
      memory: 256Mi
backupDaemon:
  resources:
    requests:
      cpu: 50m
      memory: 128Mi
    limits:
      cpu: 100m
      memory: 256Mi
```

</details>

# Parameters

The RabbitMQ installation parameters must be specified in the **values.yaml** file.
<!-- #GFCFilterMarkerStart# -->
Refer to [values.yaml](/operator/charts/helm/rabbitmq/values.yaml).
<!-- #GFCFilterMarkerEnd# -->
It can be done manually or automatically through jobs.

## Cloud Integration Parameters

| Parameter                     | Type    | Mandatory | Default value | Description                                                                                                                                                                                                                                                                                                                                                                                             |
|-------------------------------|---------|-----------|---------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| INFRA_RABBITMQ_ADMIN_USERNAME | string  | yes       | `""`          | This parameter specifies the RabbitMQ default user. It has no default value and the value needs to be specified.                                                                                                                                                                                                                                                                                        |
| INFRA_RABBITMQ_ADMIN_PASSWORD | string  | yes       | `""`          | This parameter specifies the RabbitMQ default password. It has no default value and the value needs to be specified.                                                                                                                                                                                                                                                                                    |
| MONITORING_ENABLED            | boolean | no        | `false`       | This parameter specifies if RabbitMQ Prometheus monitoring needs to be installed. By default, Prometheus monitoring is not installed. For more information, refer to [RabbitMQ Operator Service Monitoring](/docs/public/monitoring.md) in the **Cloud Platform Monitoring Guide**.                                                                                                                     |
| STORAGE_RWO_CLASS             | string  | yes       | `""`          | This parameter specifies the RabbitMQ storage class. When used for deployment on local PVs, it must be the same as what is set on the PVs. When the storage class is not set, use `''`. When the storage class is empty, use `"''"` (`"\"\""` with ESCAPE_SEQUENCE=true;). **This parameter is required for installation using storage class**. |
| INFRA_RABBITMQ_FS_GROUP       | integer | no        |               | Specifies the group ID used inside RabbitMQ pods.                                                                                                                                                                                                                                                                                                                                                           |
| INFRA_RABBITMQ_REPLICAS       | integer | no        |               | Specifies the RabbitMQ replicas count.                                                                                                                                                                                                                                                                                                                                                                      |
| S3_ENDPOINT                   | string  | no        | `""`          | This parameter specifies the URL of S3 storage.                                                                                                                                                                                                                                                                                                                                                         |
| S3_ACCESSKEY                  | string  | no        | `""`          | This parameter specifies the key ID for S3 storage.                                                                                                                                                                                                                                                                                                                                                     |
| S3_SECRETKEY                  | string  | no        | `""`          | This parameter specifies the secret for S3 storage.                                                                                                                                                                                                                                                                                                                                                     |

## Global

| Parameter                                  | Type    | Mandatory | Default value            | Description                                                                                                                                                                                                                                                                                                                                                                           |
|--------------------------------------------|---------|-----------|--------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| loglevel                                   | string  | no        | `INFO`                   | This parameter specifies the RabbitMQ operator logging level. It can be set to `DEBUG`, `INFO`, and so on.                                                                                                                                                                                                                                                                            |
| operatorDeleteResources                    | boolean | no        | `False`                  | This parameter specifies whether the RabbitMQ operator should delete all RabbitMQ resources when the RabbitMQ Custom Resource (CR) is deleted.<br> **Warning**: If it is set to `True`, the RabbitMQ operator must be up and running when deleting the CR. Otherwise, the delete operation may be stuck for an extended period of time, and may stop you from deleting the namespace. |
| operatorImage                              | string  | no        | calculated automatically | This parameter specifies the RabbitMQ operator image. The image is included in the manifest.                                                                                                                                                                                                                                                                                          |
| global.customLabels                        | object  | no        | `{}`                     | This parameter allows specifying custom labels for all pods that are related to the RabbitMQ service. These labels can be overridden by local custom labels.                                                                                                                                                                                                                          |
| global.securityContext                     | object  | no        | `{}`                     | This parameter allows specifying pod security context for all pods that are related to the RabbitMQ service. These labels can be overridden by local custom labels.                                                                                                                                                                                                                   |
| global.disableRunAsNonRoot                 | boolean | no        | `false`                  | This parameter specifies whether to disable `runAsNonRoot` for all RabbitMQ services.                                                                                                                                                                                                                                                                                                 |
| global.podReadinessTimeout                 | integer | no        | `180`                    | This parameter specifies timeout in seconds for how long the operator should wait for the pods to be ready for each service.                                                                                                                                                                                                                                                          |
| global.tls.enabled                         | boolean | no        | `false`                  | This parameter specifies whether to use SSL for all RabbitMQ services.                                                                                                                                                                                                                                                                                                                |
| global.tls.cipherSuites                    | list    | no        | `[]`                     | This parameter specifies the list of cipher suites that are used to negotiate the security settings for a network connection using TLS or SSL network protocol.                                                                                                                                                                                                                       |
| global.tls.allowNonencryptedAccess         | boolean | no        | `true`                   | This parameter specifies whether to allow non-encrypted access to RabbitMQ services, if it is possible.                                                                                                                                                                                                                                                                               |
| global.tls.generateCerts.enabled           | boolean | no        | `true`                   | This parameter specifies whether to generate SSL certificates.                                                                                                                                                                                                                                                                                                                        |
| global.tls.generateCerts.certProvider      | string  | no        | `cert-manager`           | This parameter specifies the provider used to generate SSL certificates. The possible values are `helm` and `cert-manager`.                                                                                                                                                                                                                                                           |
| global.tls.generateCerts.durationDays      | integer | no        | `365`                    | This parameter specifies the SSL certificate validity duration in days.                                                                                                                                                                                                                                                                                                               |
| global.tls.generateCerts.clusterIssuerName | string  | no        | `""`                     | This parameter specifies the name of the ClusterIssuer resource. If the parameter is not set or empty, the Issuer resource in the current Kubernetes namespace is used. It is used when the `global.tls.generateCerts.certProvider` parameter is set to cert-manager. **Important**: This parameter must be set for the production environment.                                       |
| global.cloudIntegrationEnabled             | boolean | no        | true                     | This parameter specifies whether to apply [Cloud Integration Parameters](#cloud-integration-parameters) instead of parameters described in RabbitMQ. If it is set to `false` or global parameter is absent, corresponding parameter from RabbiMQ is applied.                                                                                                                          |
| allowEvents                                | boolean | no        | `false`                  | This parameter specifies whether the RabbitMQ operator should have permissions to create Kubernetes events.                                                                                                                                                                                                                                                                           |

## Operator

| Parameter                                           | Type    | Mandatory | Default value            | Description                                                                                                                                                                                                                                                                                                                     |
|-----------------------------------------------------|---------|-----------|--------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| operator.resources.limits.cpu                       | string  | no        | 100m                     | This parameter specifies the RabbitMQ operator CPU limits.                                                                                                                                                                                                                                                                      |
| operator.resources.limits.memory                    | string  | no        | 100Mi                    | This parameter specifies the RabbitMQ operator CPU limits.                                                                                                                                                                                                                                                                      |
| operator.resources.requests.cpu                     | string  | no        | 100m                     | This parameter specifies the RabbitMQ operator CPU requests.                                                                                                                                                                                                                                                                    |
| operator.resources.requests.memory                  | string  | no        | 100Mi                    | This parameter specifies the RabbitMQ operator memory requests.                                                                                                                                                                                                                                                                 |
| operator.pullPolicy                                 | string  | no        | `IfNotPresent`           | This parameter specifies the RabbitMQ operator imagePullPolicy.                                                                                                                                                                                                                                                                 |
| operator.customLabels                               | object  | no        | `{}`                     | This parameter allows specifying custom labels for the RabbitMQ service operator pod.                                                                                                                                                                                                                                           |
| operator.securityContext                            | object  | no        | `{}`                     | This parameter allows specifying the pod security context for the RabbitMQ service operator pod.                                                                                                                                                                                                                                |
| operator.priorityClassName                          | string  | no        | `""`                     | This parameter specifies the priority class name for operator pod. You should create the priority class beforehand. For more information about this feature, refer to [https://kubernetes.io/docs/concepts/configuration/pod-priority-preemption/](https://kubernetes.io/docs/concepts/configuration/pod-priority-preemption/). |
| operator.affinity                                   | object  | no        | `{}`                     | This parameter specifies affinity rules for the operator.                                                                                                                                                                                                                                                                       |
| operator.restartScheduler.enabled                   | boolean | no        | `true`                   | This parameter specifies whether to periodically restart the operator pod. It is applicable only for an enabled disaster recovery.                                                                                                                                                                                              |
| operator.restartScheduler.customLabels              | object  | no        | `{}`                     | This parameter allows specifying custom labels for the Pod Restarter.                                                                                                                                                                                                                                                           |
| operator.restartScheduler.dockerImage               | string  | no        | calculated automatically | This parameter specifies the the Pod Restarter Docker image.                                                                                                                                                                                                                                                                    |
| operator.restartScheduler.schedule                  | string  | no        | `0 0 * * *`              | This parameter specifies the schedule (in CRON format) to restart the operator pod.                                                                                                                                                                                                                                             |
| operator.restartScheduler.affinity                  | object  | no        | `{}`                     | This parameter specifies the Pod Restarter affinity rules.                                                                                                                                                                                                                                                                      |
| operator.restartScheduler.nodeSelector              | object  | no        | `{}`                     | This parameter specifies the Pod Restarter node selector.                                                                                                                                                                                                                                                                       |
| operator.restartScheduler.securityContext           | object  | no        | `{}`                     | This parameter specifies the Pod Restarter security context. It should be filed as `runAsUser: 1000` for non-root privileges' environments.                                                                                                                                                                                     |
| operator.restartScheduler.resources.limits.cpu      | string  | no        | 50m                      | This parameter specifies the Pod Restarter CPU limits.                                                                                                                                                                                                                                                                          |
| operator.restartScheduler.resources.limits.memory   | string  | no        | 128Mi                    | This parameter specifies the Pod Restarter memory limits.                                                                                                                                                                                                                                                                       |
| operator.restartScheduler.resources.requests.cpu    | string  | no        | 15m                      | This parameter specifies the Pod Restarter CPU requests.                                                                                                                                                                                                                                                                        |
| operator.restartScheduler.resources.requests.memory | string  | no        | 128Mi                    | This parameter specifies the Pod Restarter memory requests.                                                                                                                                                                                                                                                                     |

## External RabbitMQ

| Parameter                      | Type    | Mandatory | Default value | Description                                                                                                                                      |
|--------------------------------|---------|-----------|---------------|--------------------------------------------------------------------------------------------------------------------------------------------------|
| externalRabbitmq.enabled       | boolean | no        | `false`       | This parameter specifies the external RabbitMQ usage without installing RabbitMQ to the current namespace.                                       |
| externalRabbitmq.url           | string  | no        |               | This parameter specifies the external RabbitMQ URL.                                                                                              |
| externalRabbitmq.username      | string  | no        |               | This parameter specifies the external RabbitMQ username.                                                                                         |
| externalRabbitmq.password      | string  | no        |               | This parameter specifies the external RabbitMQ password.                                                                                         |
| externalRabbitmq.replicas      | integer | no        | 0             | This parameter specifies the number of external RabbitMQ replicas.                                                                               |
| externalRabbitmq.clusterName   | string  | no        |               | This parameter specifies the external RabbitMQ cluster name.                                                                                     |
| externalRabbitmq.enableSsl     | boolean | no        | `false`       | This parameter specifies whether to use SSL to connect RabbitMQ.                                                                                 |
| externalRabbitmq.sslSecretName | string  | no        | `""`          | This parameter specifies the secret that contains SSL certificates. It is required if the `externalRabbitmq.enableSsl` parameter is set to true. |

## Disaster Recovery

| Parameter                                                         | Type    | Mandatory | Default value               | Description                                                                                                                                                                                                                                                                                                   |
|-------------------------------------------------------------------|---------|-----------|-----------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| disasterRecovery.image                                            | string  | no        | calculated automatically    | This parameter specifies the Disaster Recovery RabbitMQ operator container image.                                                                                                                                                                                                                             |
| disasterRecovery.mode                                             | string  | no        | `""`                        | This parameter specifies the Disaster Recovery mode. If the parameter is empty, the Disaster Recovery installation is disabled. The possible values are `active`,`standby`, and `disabled`.                                                                                                                   |
| disasterRecovery.region                                           | string  | no        | `""`                        | This parameter specifies the Disaster Recovery region. The `region` parameter is included in every RabbitMQ backup if the Disaster Recovery installation mode is enabled. `Active` and `standby` RabbitMQ clusters must have different `region` parameters.                                                   |
| disasterRecovery.siteManagerEnabled                               | boolean | no        | `true`                      | This parameter enables the integration with Site Manager tools.                                                                                                                                                                                                                                               |
| disasterRecovery.afterServices                                    | list    | no        | `[]`                        | This parameter specifies the list of `SiteManager` names for services after which the RabbitMQ service switchover is to be run.                                                                                                                                                                               |
| disasterRecovery.httpAuth.enabled                                 | boolean | no        | `false`                     | This parameter specifies if authentication should be enabled or not.                                                                                                                                                                                                                                          |
| disasterRecovery.httpAuth.smSecureAuth                            | boolean | no        | false                       | Whether the `smSecureAuth` mode is enabled for Site Manager or not.                                                                                                                                                                                                                                           |
| disasterRecovery.httpAuth.smNamespace                             | string  | no        | `site-manager`              | This parameter specifies the name of the Kubernetes namespace from which the site manager API calls are done.                                                                                                                                                                                                 |
| disasterRecovery.httpAuth.smServiceAccountName                    | string  | no        | `sm-auth-sa`                | This parameter specifies the name of the Kubernetes Service Account under which the site manager API calls are done.                                                                                                                                                                                          |
| disasterRecovery.httpAuth.customAudience                          | string  | no        | sm-services                 | The name of custom audience for rest api token, that is used to connect with services. It is necessary if Site Manager installed with `smSecureAuth=true` and has applied custom audience (`sm-services` by default). It is considered if `disasterRecovery.httpAuth.smSecureAuth` parameter is set to `true` |
| disasterRecovery.httpAuth.restrictedEnvironment                   | boolean | no        | `false`                     | If the parameter is `true`, the `system:auth-delegator` cluster role binding will not be created by deployer and must be created manually.                                                                                                                                                                    |
| disasterRecovery.resources.limits.cpu                             | string  | no        | 32m                         | This parameter specifies the Disaster Recovery RabbitMQ operator container CPU limits.                                                                                                                                                                                                                        |
| disasterRecovery.resources.limits.memory                          | string  | no        | 32Mi                        | This parameter specifies the Disaster Recovery RabbitMQ operator container memory limits.                                                                                                                                                                                                                     |
| disasterRecovery.resources.requests.cpu                           | string  | no        | 10m                         | This parameter specifies the Disaster Recovery RabbitMQ operator container CPU requests.                                                                                                                                                                                                                      |
| disasterRecovery.resources.requests.memory                        | string  | no        | 10Mi                        | This parameter specifies the Disaster Recovery RabbitMQ operator container memory requests.                                                                                                                                                                                                                   |
| disasterRecovery.tls.enabled                                      | boolean | no        | `true`                      | This parameter specifies whether to use SSL to connect DRD. For more information about DRD SSL, refer to the [TLS Encryption for RabbitMQ](/docs/public/TLS.md) chapter.                                                                                                                                      |
| disasterRecovery.tls.certificates.crt                             | string  | no        | `""`                        | The certificate in BASE64 format. It is required if `global.tls.enabled` parameter is set to `true`, `global.tls.generateCerts.certProvider` parameter is set to `helm` and `global.tls.generateCerts.enabled` parameter is set to `false`.                                                                   |
| disasterRecovery.tls.certificates.key                             | string  | no        | `""`                        | The private key in BASE64 format. It is required if `global.tls.enabled` parameter is set to `true`, `global.tls.generateCerts.certProvider` parameter is set to `helm` and `global.tls.generateCerts.enabled` parameter is set to `false`.                                                                   |
| disasterRecovery.tls.certificates.ca                              | string  | no        | `""`                        | The root CA certificate in BASE64 format. It is required if `global.tls.enabled` parameter is set to `true`, `global.tls.generateCerts.certProvider` parameter is set to `helm` and `global.tls.generateCerts.enabled` parameter is set to `false`.                                                           |
| disasterRecovery.tls.secretName                                   | string  | no        | `"rabbitmq-drd-tls-secret"` | This parameter specifies the secret that contains SSL certificates. It is required if the `disasterRecovery.tls.enabled` parameter is set to true and `global.tls.generateCerts.enabled` is set to false.                                                                                                     |
| disasterRecovery.tls.cipherSuites                                 | list    | no        | `[]`                        | This parameter specifies the list of cipher suites that are used to negotiate the security settings for a network connection using TLS or SSL network protocol and overrides the `global.tls.cipherSuites` parameter.                                                                                         |
| disasterRecovery.tls.subjectAlternativeName.additionalDnsNames    | list    | no        | `[]`                        | This parameter specifies the list of additional DNS names to be added to the "Subject Alternative Name" field of the SSL certificate.                                                                                                                                                                         |
| disasterRecovery.tls.subjectAlternativeName.additionalIpAddresses | list    | no        | `[]`                        | This parameter specifies the list of additional IP addresses to be added to the "Subject Alternative Name" field of the SSL certificate.                                                                                                                                                                      |
| disasterRecovery.noWait                                           | boolean | no        | `false`                     | If the parameter is `true` and there is no backup from other region, then the restore process is skipped without fail.                                                                                                                                                                                        |

## RabbitMQ

| Parameter                                                 | Type    | Mandatory | Default value                                                                                                           | Description                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
|-----------------------------------------------------------|---------|-----------|-------------------------------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| rabbitmq.eventLogging                                     | boolean | no        | `true`                                                                                                                  | This parameter specifies whether to enable event logging in RabbitMQ. For more information about RabbitMQ event logging, refer to the [RabbitMQ Operator Event Logging](/docs/public/eventLogging.md) section in _Cloud Platform Maintenance Guide_.                                                                                                                                                                                                                                                                                                                           |
| rabbitmq.tls.enabled                                      | boolean | no        | `true`                                                                                                                  | This parameter specifies whether to use SSL to connect RabbitMQ. For more information about RabbitMQ with SSL, refer to the [TLS Encryption for RabbitMQ](/docs/public/TLS.md) chapter.                                                                                                                                                                                                                                                                                                                                                                                        |
| rabbitmq.tls.certificates.crt                             | string  | no        | `""`                                                                                                                    | The certificate in BASE64 format. It is required if `global.tls.enabled` parameter is set to `true`, `global.tls.generateCerts.certProvider` parameter is set to `helm` and `global.tls.generateCerts.enabled` parameter is set to `false`.                                                                                                                                                                                                                                                                                                                                    |
| rabbitmq.tls.certificates.key                             | string  | no        | `""`                                                                                                                    | The private key in BASE64 format. It is required if `global.tls.enabled` parameter is set to `true`, `global.tls.generateCerts.certProvider` parameter is set to `helm` and `global.tls.generateCerts.enabled` parameter is set to `false`.                                                                                                                                                                                                                                                                                                                                    |
| rabbitmq.tls.certificates.ca                              | string  | no        | `""`                                                                                                                    | The root CA certificate in BASE64 format. It is required if `global.tls.enabled` parameter is set to `true`, `global.tls.generateCerts.certProvider` parameter is set to `helm` and `global.tls.generateCerts.enabled` parameter is set to `false`.                                                                                                                                                                                                                                                                                                                            |
| rabbitmq.tls.secretName                                   | string  | no        | `"rabbitmq-tls-secret"`                                                                                                 | This parameter specifies the secret that contains SSL certificates. It is required if the `rabbitmq.tls.enabled` parameter is set to true and `global.tls.generateCerts.enabled` is set to false.                                                                                                                                                                                                                                                                                                                                                                              |
| rabbitmq.tls.cipherSuites                                 | list    | no        | `[]`                                                                                                                    | This parameter specifies the list of cipher suites that are used to negotiate the security settings for a network connection using TLS or SSL network protocol and overrides the `global.tls.cipherSuites` parameter.                                                                                                                                                                                                                                                                                                                                                          |
| rabbitmq.tls.subjectAlternativeName.additionalDnsNames    | list    | no        | `[]`                                                                                                                    | This parameter specifies the list of additional DNS names to be added to the **Subject Alternative Name** field of an SSL certificate.                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| rabbitmq.tls.subjectAlternativeName.additionalIpAddresses | list    | no        | `[]`                                                                                                                    | This parameter specifies the list of additional IP addresses to be added to the **Subject Alternative Name** field of an SSL certificate.                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| rabbitmq.ingress.enabled                                  | boolean | no        | `false`                                                                                                                 | This parameter enables RabbitMQ ingress creation.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| rabbitmq.ingress.host                                     | string  | no        | `""`                                                                                                                    | This parameter specifies the name of the external RabbitMQ host. It must be complex and unique enough not to intersect with other possible external host names. For example, to generate the value for this parameter, you can use the OpenShift/Kubernetes host: If the URL to OpenShift/Kubernetes is `https://example.com:8443` and the namespace is rabbitmq-service, the host name for RabbitMQ can be `rabbitmq-rabbitmq-service.example.com`. After the deployment is completed, you can access RabbitMQ using the `https://rabbitmq-rabbitmq-service.example.com` URL. |
| rabbitmq.ingress.className                                | string  | no        | `""`                                                                                                                    | This parameter specifies the class name of RabbitMQ Ingress.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| rabbitmq.secret_change                                    | string  | no        | `1`                                                                                                                     | This parameter must be updated when the password in the RabbitMQ secret is manually changed.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| rabbitmq.tolerations                                      | list    | no        | `[]`                                                                                                                    | This parameter allows to specify tolerations in the JSON format. When specified, it affects all RabbitMQ deployment pods (operator, rabbitmq, telegraf, tests). It does not work for RabbitMQ pods in an obsolete `hostpath` configuration.                                                                                                                                                                                                                                                                                                                                    |
| rabbitmq.dockerImage                                      | string  | no        | calculated automatically                                                                                                | This parameter specifies the RabbitMQ Docker image. The image is included in the manifest.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| rabbitmq.ipv6_enabled                                     | boolean | no        | `false`                                                                                                                 | This parameter specifies whether IPv6 is enabled. Set it to `true` when RabbitMQ is installed in the IPv6 cluster. This configuration supports only RabbitMQ deployment by using storage class.                                                                                                                                                                                                                                                                                                                                                                                |
| rabbitmq.ldap.enabled                                     | boolean | no        | `false`                                                                                                                 | This parameter specifies whether to enable LDAP integration for RabbitMQ.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| rabbitmq.ldap.server                                      | string  | no        | `""`                                                                                                                    | LDAP server hostname for connection.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| rabbitmq.ldap.port                                        | integer | no        |                                                                                                                         | LDAP server port for connection.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| rabbitmq.ldap.enableSsl                                   | boolean | no        | `false`                                                                                                                 | This parameter specifies whether to use LDAPS.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| rabbitmq.ldap.dn.usernameDn                               | string  | no        | `""`                                                                                                                    | LDAP username.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| rabbitmq.ldap.dn.passwordDn                               | string  | no        | `""`                                                                                                                    | LDAP password.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| rabbitmq.ldap.dnAttribute                                 | string  | no        | `""`                                                                                                                    | Name of the attribute used to look for the user name in the directory entry.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| rabbitmq.ldap.base                                        | string  | no        | `""`                                                                                                                    | LDAP search base, for example `DC=testad,DC=local`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| rabbitmq.ldap.sslOptions.trustedCerts                     | object  | no        | `[]`                                                                                                                    | The root CA certificate of LDAPS.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| rabbitmq.ldap.advancedConfig                              | string  | no        | `"{rabbitmq_auth_backend_ldap, [{tag_queries, [{administrator, {constant, false}}, {management, {constant, true}}]}]}"` | This parameter specifies the advanced configuration properties for RabbitMQ.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| rabbitmq.clean_rabbitmq_pvs                               | boolean | no        | `false`                                                                                                                 | When set to "true", RabbitMQ tries to clean the PVs specified in the `PV_NAME` parameter. **Warning**: When upgrading RabbitMQ, setting this parameter to "true" deletes all the RabbitMQ user data from the previous installation, including messages, queues, users, vhosts, and so on.                                                                                                                                                                                                                                                                                      |
| rabbitmq.auto_reboot                                      | boolean | no        | `false`                                                                                                                 | This parameter specifies the RabbitMQ upgrade. If set to "false", the new configuration is applied, but the RabbitMQ pods are not rebooted. This means that the new configuration is not applied until the pods are rebooted for any reason (with the exception of the default password - the new password is applied even without the reboot). If set to "true", the RabbitMQ pods are rebooted one after the other during the update, and it checks the cluster formation.                                                                                                   |
| rabbitmq.hostpath_configuration                           | boolean | no        | `false`                                                                                                                 | This parameter specifies whether local PVs can be used. If set to "true", RabbitMQ tries to deploy on local PVs using the PV and node values/labels provided in other parameters. If set to "false", RabbitMQ is deployed using the storage class. <br> **Note**: The `hostpath` configuration is obsolete, consider using the storage class.                                                                                                                                                                                                                                  |
| rabbitmq.validate_state                                   | boolean | no        | `false`                                                                                                                 | This parameter specifies the validation of cluster formation during the RabbitMQ installation.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| rabbitmq.custom_params.rabbitmq_cluster_name              | string  | no        | `rabbitmq`                                                                                                              | This parameter specifies the RabbitMQ cluster_name. It is used to identify a cluster, and by the federation and Shovel plugins to record the origin or path of transferred messages. For example, `rabbitmq`.                                                                                                                                                                                                                                                                                                                                                                  |
| rabbitmq.custom_params.rabbitmq_vm_memory_high_watermark  | string  | no        | `80%`                                                                                                                   | This parameter specifies the RabbitMQ vm_memory_high_watermark. It sets RabbitMQ memory as a percentage of the maximum available memory in a pod. For example, `80%`. For more information about the `vm_memory_high_watermark` parameter, refer to the official RabbitMQ documentation at [https://www.rabbitmq.com/memory.html](https://www.rabbitmq.com/memory.html).                                                                                                                                                                                                       |
| rabbitmq.custom_params.rabbitmq_default_user              | string  | yes       |                                                                                                                         | This parameter specifies the RabbitMQ default user. It has no default value and the value needs to be specified.                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| rabbitmq.custom_params.rabbitmq_default_password          | string  | yes       |                                                                                                                         | This parameter specifies the RabbitMQ default password. It has no default value and the value needs to be specified.                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| rabbitmq.volumes                                          | list    | no        | `[]`                                                                                                                    | This parameter specifies the RabbitMQ PVs that can be used. It is only for local PV installation. **This parameter or `rabbitmq.selectors` is required for local PV installation**.                                                                                                                                                                                                                                                                                                                                                                                            |
| rabbitmq.selectors                                        | object  | no        | `{}`                                                                                                                    | This parameter can be used instead of `rabbitmq.volumes` to specify RabbitMQ PVs. It is a list of labels that is used to bind suitable persistent volumes with the persistent volume claims.                                                                                                                                                                                                                                                                                                                                                                                   |
| rabbitmq.nodes                                            | list    | no        | `[]`                                                                                                                    | This parameter specifies the nodes where RabbitMQ PVs are located. It is only for local PV installation. **This parameter is required for local PV installation**.                                                                                                                                                                                                                                                                                                                                                                                                             |
| rabbitmq.replicas                                         | integer | no        | `3`                                                                                                                     | This parameter specifies the RabbitMQ replicas.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| rabbitmq.nodePortService.install                          | boolean | no        | `false`                                                                                                                 | This parameter specifies if RabbitMQ node port service should be applied. The service exposes RabbitMQ management plugin and AMPQ on specified ports.                                                                                                                                                                                                                                                                                                                                                                                                                          |
| rabbitmq.nodePortService.mgmtNodePort                     | integer | no        |                                                                                                                         | This parameter specifies the node port for RabbitMQ management plugin. If not specified, a port provided by OpenShift is used.                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| rabbitmq.nodePortService.amqpNodePort                     | integer | no        |                                                                                                                         | This parameter specifies the node port for AMQP protocol. If not specified, a port provided by OpenShift is used.                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| rabbitmq.resources.limits.cpu                             | string  | no        | 1                                                                                                                       | This parameter specifies the RabbitMQ CPU limits.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| rabbitmq.resources.limits.memory                          | string  | no        | 2Gi                                                                                                                     | This parameter specifies the RabbitMQ memory limits.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| rabbitmq.resources.requests.cpu                           | string  | no        | 1                                                                                                                       | This parameter specifies the RabbitMQ CPU requests.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| rabbitmq.resources.requests.memory                        | string  | no        | 2Gi                                                                                                                     | This parameter specifies the RabbitMQ memory requests.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| rabbitmq.resources.storage                                | string  | no        | `1024Mi`                                                                                                                | This parameter specifies the RabbitMQ storage size.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| rabbitmq.resources.storageclass                           | string  | yes       | `""`                                                                                                                    | This parameter specifies the RabbitMQ storage class. When used for deployment on local PVs, it must be the same as what is set on the PVs. When the storage class is not set, use `''` . When the storage class is empty, use `"''"` (`"\"\""` with ESCAPE_SEQUENCE=true;). **This parameter is required for installation using storage class**.                                                                                                                                                                        |
| rabbitmq.enabledPlugins                                   | list    | no        | `[]`                                                                                                                    | This parameter specifies the RabbitMQ enabled plugins. For example, `["rabbitmq_shovel", "rabbitmq_federation"]`.                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| rabbitmq.customConfigProperties                           | list    | no        | `[]`                                                                                                                    | This parameter specifies the custom configuration properties for RabbitMQ (`rabbitmq.conf`).                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| rabbitmq.customAdvancedProperties                         | list    | no        | `[]`                                                                                                                    | This parameter specifies the advanced configuration properties for RabbitMQ (`advanced.config`) in multi-line format.                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| rabbitmq.environmentVariables                             | list    | no        | `[]`                                                                                                                    | This parameter specifies the list of additional environment variables for RabbitMQ in `key=value` format. For example, `["RABBITMQ_PROPERTY_NAME=propertyValue"]`.                                                                                                                                                                                                                                                                                                                                                                                                             |
| rabbitmq.affinity                                         | object  | no        | `{}`                                                                                                                    | This parameter specifies affinity rules for RabbitMQ pods.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| rabbitmq.customLabels                                     | object  | no        | `{}`                                                                                                                    | This parameter allows specifying custom labels for all RabbitMQ pods.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| rabbitmq.customAnnotations                                | object  | no        | `{}`                                                                                                                    | This parameter allows specifying custom annotations for all RabbitMQ pods.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| rabbitmq.securityContext                                  | object  | no        | `{}`                                                                                                                    | This parameter parameter allows specifying pod security context for the RabbitMQ pods.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| rabbitmq.priorityClassName                                | string  | no        | `""`                                                                                                                    | This parameter specifies the priority class name for RabbitMQ pods. You should create the priority class beforehand. For more information about this feature, refer to [https://kubernetes.io/docs/concepts/configuration/pod-priority-preemption/](https://kubernetes.io/docs/concepts/configuration/pod-priority-preemption/).                                                                                                                                                                                                                                               |
| rabbitmq.livenessProbe                                    | object  | no        | `{}`                                                                                                                    | This parameter parameter allows specifying liveness probe for the RabbitMQ pods.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| rabbitmq.readinessProbe                                   | object  | no        | `{}`                                                                                                                    | This parameter parameter allows specifying readiness probe for the RabbitMQ pods.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| rabbitmq.deleteStatefulSetOnForbiddenUpdate               | boolean | no        | `true`                                                                                                                  | This parameter specifies whether to handle a case of forbidden `rmqlocal` StatefulSet update. If it is set to `true` and operator gets "Forbidden: updates to statefulset spec for fields..." error, operator removes presented `rmqlocal` StatefulSet without deleting pods and creates `rmqlocal` StatefulSet with new parameters. If it is set to `false` and operator gets "Forbidden: updates to statefulset spec for fields..." error, operator fails with the error.                                                                                                    |

Where:

* `rabbitmq.affinity` default value is as follows:

   ```yaml
     affinity: {
       "podAntiAffinity": {
         "requiredDuringSchedulingIgnoredDuringExecution": [
           {
             "labelSelector": {
               "matchExpressions": [
                 {
                   "key": "app",
                   "operator": "In",
                   "values": [
                     "rmqlocal"
                   ]
                 }
               ]
             },
             "topologyKey": "topology.kubernetes.io/hostname"
           }
         ]
       }
     }
   ```

* `rabbitmq.livenessProbe` default value is as follows:

   ```yaml
     livenessProbe:
       initialDelaySeconds: 10
       timeoutSeconds: 15
       periodSeconds: 30
       successThreshold: 1
       failureThreshold: 30
   ```

* `rabbitmq.readinessProbe` default value is as follows:

   ```yaml
     readinessProbe:
       initialDelaySeconds: 10
       timeoutSeconds: 15
       periodSeconds: 10
       successThreshold: 1
       failureThreshold: 90
   ```

## Backup Daemon

| Parameter                                                     | Type    | Mandatory | Default value                         | Description                                                                                                                                                                                                                                         |
|---------------------------------------------------------------|---------|-----------|---------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| backupDaemon.image                                            | string  | no        | calculated automatically              | This parameter specifies the Docker image for RabbitMQ backup daemon. The image is included in the manifest.                                                                                                                                        |
| backupDaemon.enabled                                          | boolean | no        | `false`                               | This parameter enables the RabbitMQ backup daemon deployment.                                                                                                                                                                                       |
| backupDaemon.tls.enabled                                      | boolean | no        | `true`                                | This parameter specifies whether to use SSL to connect backup daemon. For more information about backup daemon SSL, refer to the [TLS Encryption for RabbitMQ](/docs/public/TLS.md) chapter.                                                        |
| backupDaemon.tls.certificates.crt                             | string  | no        | `""`                                  | The certificate in BASE64 format. It is required if `global.tls.enabled` parameter is set to `true`, `global.tls.generateCerts.certProvider` parameter is set to `helm` and `global.tls.generateCerts.enabled` parameter is set to `false`.         |
| backupDaemon.tls.certificates.key                             | string  | no        | `""`                                  | The private key in BASE64 format. It is required if `global.tls.enabled` parameter is set to `true`, `global.tls.generateCerts.certProvider` parameter is set to `helm` and `global.tls.generateCerts.enabled` parameter is set to `false`.         |
| backupDaemon.tls.certificates.ca                              | string  | no        | `""`                                  | The root CA certificate in BASE64 format. It is required if `global.tls.enabled` parameter is set to `true`, `global.tls.generateCerts.certProvider` parameter is set to `helm` and `global.tls.generateCerts.enabled` parameter is set to `false`. |
| backupDaemon.tls.secretName                                   | string  | no        | `"rabbitmq-backup-daemon-tls-secret"` | This parameter specifies the secret that contains SSL certificates. It is required if `backupDaemon.tls.enabled parameter` is set to true and `global.tls.generateCerts.enabled` is set to false.                                                   |
| backupDaemon.tls.subjectAlternativeName.additionalDnsNames    | list    | no        | `[]`                                  | This parameter specifies the list of additional DNS names to be added to the **Subject Alternative Name** field of an SSL certificate.                                                                                                              |
| backupDaemon.tls.subjectAlternativeName.additionalIpAddresses | list    | no        | `[]`                                  | This parameter specifies the list of additional IP addresses to be added to the **Subject Alternative Name** field of an SSL certificate.                                                                                                           |
| backupDaemon.storage                                          | string  | no        | `1Gi`                                 | This parameter specifies the storage disk size of the attached volume.                                                                                                                                                                              |
| backupDaemon.storageClass                                     | string  | yes       | `null`                                | This parameter specifies the storage class name.                                                                                                                                                                                                    |
| backupDaemon.persistentVolume                                 | string  | no        | `null`                                | This parameter specifies the persistent volume name.                                                                                                                                                                                                |
| backupDaemon.backupSchedule                                   | string  | no        | `"0 0 * * *"`                         | This parameter specifies the backup schedule.                                                                                                                                                                                                       |
| backupDaemon.evictionPolicy                                   | string  | no        | `"0/1d,7d/delete"`                    | This parameter specifies the eviction policy.                                                                                                                                                                                                       |
| backupDaemon.affinity                                         | object  | no        | `{}`                                  | This parameter specifies the affinity rules for backup daemon.                                                                                                                                                                                      |
| backupDaemon.tolerations                                      | list    | no        | `[]`                                  | This parameter specifies the tolerations for backup daemon.                                                                                                                                                                                         |
| backupDaemon.nodeSelector                                     | object  | no        | `{}`                                  | This parameter specifies the node selector for backup daemon.                                                                                                                                                                                       |
| backupDaemon.securityContext                                  | object  | yes       | `{}`                                  | This parameter specifies the security context for backup daemon.                                                                                                                                                                                    |
| backupDaemon.priorityClassName                                | string  | no        | `""`                                  | This parameter specifies the priority class name for backup daemon.                                                                                                                                                                                 |
| backupDaemon.resources.limits.cpu                             | string  | no        | 200m                                  | This parameter specifies the RabbitMQ backup daemon CPU limits.                                                                                                                                                                                     |
| backupDaemon.resources.limits.memory                          | string  | no        | 256Mi                                 | This parameter specifies the RabbitMQ backup daemon memory limits.                                                                                                                                                                                  |
| backupDaemon.resources.requests.cpu                           | string  | no        | 25m                                   | This parameter specifies the RabbitMQ backup daemon CPU requests.                                                                                                                                                                                   |
| backupDaemon.resources.requests.memory                        | string  | no        | 64Mi                                  | This parameter specifies the RabbitMQ backup daemon memory requests.                                                                                                                                                                                |
| backupDaemon.s3.enabled                                       | boolean | no        | `false`                               | This parameter enables saving RabbitMQ backups to S3 storage.                                                                                                                                                                                       |
| backupDaemon.s3.sslVerify                                     | boolean | no        | `true`                                | This parameter specifies whether or not to verify SSL certificates for S3 connections.                                                                                                                                                              |
| backupDaemon.s3.sslSecretName                                 | string  | no        | `""`                                  | This parameter specifies name of the secret with CA certificate for S3 connections. If secret not exists and parameter `backupDaemon.s3.sslCert` is specified secret will be created, else boto3 certificates will be used.                         |
| backupDaemon.s3.sslCert                                       | string  | no        | `""`                                  | The root CA certificate in BASE64 format. It is required if pre-created secret with certificates not exists and default boto3 certificates will not be used.                                                                                        |
| backupDaemon.s3.url                                           | string  | no        |                                       | This parameter specifies the URL of S3 storage.                                                                                                                                                                                                     |
| backupDaemon.s3.bucket                                        | string  | no        |                                       | This parameter specifies the bucket in S3 storage.                                                                                                                                                                                                  |
| backupDaemon.s3.keyId                                         | string  | no        |                                       | This parameter specifies the key ID for S3 storage.                                                                                                                                                                                                 |
| backupDaemon.s3.keySecret                                     | string  | no        |                                       | This parameter specifies the secret for S3 storage.                                                                                                                                                                                                 |
| backupDaemon.customLabels                                     | object  | no        | `{}`                                  | This parameter allows specifying custom labels for the RabbitMQ Service Backup daemon pod.                                                                                                                                                          |
| backupDaemon.securityContext                                  | object  | no        | `{}`                                  | This parameter allows specifying pod security context for the RabbitMQ Service Backup daemon pod.                                                                                                                                                   |

## Tests

| Parameter                       | Type    | Mandatory | Default value            | Description                                                                                                                                                                                                                                                                                                                                          |
|---------------------------------|---------|-----------|--------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| tests.dockerImage               | string  | no        | calculated automatically | This parameter specifies the Docker image for RabbitMQ robot tests. The image is included in the manifest.                                                                                                                                                                                                                                           |
| tests.runTests                  | boolean | no        | `false`                  | This parameter specifies whether to run tests after installation or after upgrade.                                                                                                                                                                                                                                                                   |
| tests.rabbitIsManagedByOperator | boolean | no        | `true`                   | This parameter specifies whether RabbitMQ is managed by Kubernetes operator.                                                                                                                                                                                                                                                                         |
| tests.runTestsOnly              | boolean | no        | `false`                  | This parameter can be specified during update. If set to "true", only the tests run without other changes.                                                                                                                                                                                                                                           |
| tests.waitTestResultOnJob       | boolean | no        | `false`                  | This parameter specifies whether to wait for integration tests' result on job.                                                                                                                                                                                                                                                                       |
| tests.tags                      | string  | no        | `smoke`                  | This parameter specifies the tests' tags such as `all`, `persistence`, `smoke`, `ha`, and so on. </br>It specifies the tags combined together with AND, OR, and NOT operators that select the test cases to run.</br> The information about available tags can be found in [Integration Test Tags' Description](#integration-test-tags-description). |
| tests.statusWritingEnabled      | boolean | no        | `true`                   | This parameter specifies whether the status of Integration tests' execution is to be written to deployment or not.                                                                                                                                                                                                                                   |
| tests.isShortStatusMessage      | boolean | no        | `true`                   | This parameter specifies whether the status message contains only the first line of **result.txt** file or not. The parameter does not matter if the statusWritingEnabled parameter is not true.                                                                                                                                                     |
| tests.timeout                   | integer | no        | `60`                     | This parameter specifies the tests' timeout in seconds.                                                                                                                                                                                                                                                                                              |
| tests.rabbitmq_port             | integer | no        | `15672`                  | This parameter specifies the RabbitMQ port number of http-connection.                                                                                                                                                                                                                                                                                |
| tests.amqp_port                 | integer | no        | `5672`                   | This parameter specifies the RabbitMQ port number of amqp-connection.                                                                                                                                                                                                                                                                                |
| tests.resources.requests.memory | string  | no        | `256Mi`                  | This parameter specifies the minimum amount of memory the container should use.                                                                                                                                                                                                                                                                      |
| tests.resources.requests.cpu    | string  | no        | `200m`                   | This parameter specifies the minimum number of CPUs the container should use.                                                                                                                                                                                                                                                                        |
| tests.resources.limits.memory   | string  | no        | `256Mi`                  | This parameter specifies the maximum amount of memory the container can use.                                                                                                                                                                                                                                                                         |
| tests.resources.limits.cpu      | string  | no        | `200m`                   | This parameter specifies the maximum number of CPUs the container can use.                                                                                                                                                                                                                                                                           |
| tests.customLabels              | object  | no        | `{}`                     | This parameter allows specifying custom labels for the RabbitMQ Service integration tests' pod.                                                                                                                                                                                                                                                      |
| tests.securityContext           | object  | no        | `{}`                     | This parameter allows specifying the pod security context for the RabbitMQ Service integration tests' pod.                                                                                                                                                                                                                                           |
| tests.priorityClassName         | string  | no        | `""`                     | This parameter specifies the priority class name for tests pod. You should create the priority class beforehand. For more information about this feature, refer to [https://kubernetes.io/docs/concepts/configuration/pod-priority-preemption/](https://kubernetes.io/docs/concepts/configuration/pod-priority-preemption/).                         |
| tests.affinity                  | object  | no        | `{}`                     | This parameter allows specifying the affinity for the RabbitMQ Service integration tests' pod.                                                                                                                                                                                                                                                       |
| tests.prometheusUrl             | string  | no        | `""`                     | The URL (with schema and port) to Prometheus. For example, <http://prometheus.cloud.openshift.sdntest.example.com:80>. This parameter must be specified if you want to run integration tests with 'alerts' tag.                                                                                                                                      |
| tests.requestTimeout            | integer | no        | 60                       | This parameter specifies request timeout which should be used during the performing test actions.                                                                                                                                                                                                                                                    |

### Integration test tags description

* `all` tag runs all presented tests.
* `backup` tag runs all tests connected to backup daemon scenarios.
* `basic` tag runs all tests connected to basic scenarios.
* `persistence` tag runs all tests connected to persistence scenarios.
* `smoke` tag runs tests to reveal simple failures.
* `cluster` tag runs all tests connected to cluster testing scenarios.
* `ha` tag runs all tests connected to HA scenarios.
* `alerts` tag runs all tests connected to Prometheus alerts cases.
* `rabbitmq_images` tag runs `Test Hardcoded Images` test.

## Monitoring

| Parameter                          | Type    | Mandatory | Default value            | Description                                                                                                                                                                                                                                                                                                                       |
|------------------------------------|---------|-----------|--------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| rabbitmqPrometheusMonitoring       | boolean | no        | `false`                  | This parameter specifies if RabbitMQ Prometheus monitoring needs to be installed. By default, Prometheus monitoring is not installed. For more information, refer to [RabbitMQ Operator Service Monitoring](/docs/public/monitoring.md) in the _Cloud Platform Monitoring Guide_.                                                 |
| rabbitmq.perQueueMetrics           | boolean | no        | `false`                  | This parameter enables per queue metrics in the `rabbitmq_prometheus` plugin.                                                                                                                                                                                                                                                     |
| telegraf.install                   | boolean | no        | `false`                  | This parameter specifies if the RabbitMQ Telegraf monitoring agent needs to be installed. For more information, refer to [RabbitMQ Service Monitoring](/docs/public/monitoring.md) in the _Cloud Platform Monitoring Guide_.<br>**Note**: This option is designed to work only with OpenShift environments.                       |
| telegraf.resources.limits.cpu      | string  | no        | 150m                     | This parameter specifies the telegraf CPU limits.                                                                                                                                                                                                                                                                                 |
| telegraf.resources.limits.memory   | string  | no        | 150Mi                    | This parameter specifies the telegraf memory limits.                                                                                                                                                                                                                                                                              |
| telegraf.resources.requests.cpu    | string  | no        | 150m                     | This parameter specifies the telegraf CPU requests.                                                                                                                                                                                                                                                                               |
| telegraf.resources.requests.memory | string  | no        | 150m                     | This parameter specifies the telegraf memory requests.                                                                                                                                                                                                                                                                            |
| telegraf.runAsUser                 | integer | no        |                          | This parameter specifies the user IDs to run processes in a Telegraf pod.                                                                                                                                                                                                                                                         |
| telegraf.influxdbDebug             | boolean | no        | `false`                  | This parameter enables/disables debug for InfluxDB.                                                                                                                                                                                                                                                                               |
| telegraf.influxdbUrl               | string  | no        | `""`                     | This parameter specifies the URL for InfluxDB.                                                                                                                                                                                                                                                                                    |
| telegraf.influxdbDatabase          | string  | no        | `rabbit_database`        | This parameter specifies the name of InfluxDB.                                                                                                                                                                                                                                                                                    |
| telegraf.influxdbUser              | string  | no        | `admin`                  | This parameter specifies the InfluxDB user.                                                                                                                                                                                                                                                                                       |
| telegraf.influxdbPassword          | string  | no        | `admin`                  | This parameter specifies the InfluxDB password.                                                                                                                                                                                                                                                                                   |
| telegraf.metricCollectionInterval  | string  | no        | `30s`                    | This parameter specifies the period of time interval for metric collection.                                                                                                                                                                                                                                                       |
| telegraf.dockerImage               | string  | no        | calculated automatically | This parameter specifies the Docker image for a Telegraf pod. The image is included in the manifest.                                                                                                                                                                                                                              |
| telegraf.customLabels              | object  | no        | `{}`                     | This parameter allows specifying custom labels for a RabbitMQ Service monitoring pod.                                                                                                                                                                                                                                             |
| telegraf.affinity                  | object  | no        | `{}`                     | This parameter allows specifying affinity for a RabbitMQ Service monitoring pod. **Note**: This parameter applies only for external monitoring.                                                                                                                                                                                   |
| telegraf.securityContext           | object  | no        | `{}`                     | This parameter parameter allows specifying pod security context for the RabbitMQ Service monitoring pod.                                                                                                                                                                                                                          |
| telegraf.priorityClassName         | string  | no        | `""`                     | This parameter specifies the priority class name for monitoring pod. You should create the priority class beforehand. For more information about this feature, refer to [https://kubernetes.io/docs/concepts/configuration/pod-priority-preemption/](https://kubernetes.io/docs/concepts/configuration/pod-priority-preemption/). |

## Status Provisioner

| Parameter                                   | Type    | Mandatory | Default value            | Description                                                                                                                                                                |
|---------------------------------------------|---------|-----------|--------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| statusProvisioner.enabled                   | boolean | no        | `true`                   | This parameter enables the Status Provisioner. **WARNING**: if you use deploy job for delivering RabbitMQ, then don't disable this parameter, because it leds to job fail. |
| statusProvisioner.dockerImage               | string  | no        | calculated automatically | This parameter specifies the Docker image for a status provisioner. The image is included in the manifest.                                                                 |
| statusProvisioner.resources.limits.cpu      | string  | no        | 50m                      | This parameter specifies the status provisioner and status provisioner cleanup CPU limits.                                                                                 |
| statusProvisioner.resources.limits.memory   | string  | no        | 50Mi                     | This parameter specifies the status provisioner and status provisioner cleanup memory limits.                                                                              |
| statusProvisioner.resources.requests.cpu    | string  | no        | 100m                     | This parameter specifies the status provisioner and status provisioner cleanup CPU requests.                                                                               |
| statusProvisioner.resources.requests.memory | string  | no        | 100m                     | This parameter specifies the status provisioner and status provisioner cleanup memory requests.                                                                            |
| statusProvisioner.lifetimeAfterCompletion   | integer | no        | `600`                    | This parameter specifies the number of seconds that a job remains alive after its completion. This functionality works only from 1.21 Kubernetes version onward.           |
| statusProvisioner.podReadinessTimeout       | integer | no        | `300`                    | This parameter specifies the timeout in seconds that the job waits for monitored resources to be ready or completed.                                                       |
| statusProvisioner.customLabels              | object  | no        | `{}`                     | This parameter specifies custom labels for a RabbitMQ Service status provisioner pod.                                                                                      |
| statusProvisioner.securityContext           | object  | no        | `{}`                     | This parameter allows specifying the pod security context for a RabbitMQ Service status provisioner pod.                                                                   |

# Installation

## Before You Begin

* Make sure the environment corresponds to the requirements in the [Prerequisites](#prerequisites) section.
* Make sure to check the [Upgrade](#upgrade) section.
* Before doing a major upgrade, it is recommended to make a backup.
* Check if the application is already installed and find the previous deployments' parameters to make changes.

### Helm

To deploy via Helm you need to prepare yaml file with custom deploy parameters and run the following
command in [RabbitMQ Chart](/operator/charts/helm/rabbitmq):

```bash
helm install [release-name] ./ -f [parameters-yaml] -n [namespace]
```

If you need to use resource profile then you can use the following command:

```bash
helm install [release-name] ./ -f ./resource-profiles/[profile-name-yaml] -f [parameters-yaml] -n [namespace]
```

**Warning**: pure Helm deployment does not support the automatic CRD upgrade procedure, so you need to perform it manually.

```bash
kubectl replace -f ./crds/crd.yaml
```

## On-Prem Examples

### HA Scheme

The minimal template for HA scheme is as follows.

```yaml
name: rabbitmq-service
rabbitmq:
  auto_reboot: true
  hostpath_configuration: false
  custom_params:
    rabbitmq_vm_memory_high_watermark: 80%
    rabbitmq_default_user: admin
    rabbitmq_default_password: admin
  replicas: 3
  resources:
    requests:
      cpu: '1'
      memory: 2Gi
    limits:
      cpu: '1'
      memory: 2Gi
    storage: 499Mi
    storageclass: {applicable_to_env_storage_class}
  securityContext:
    fsGroup: 1000
    runAsUser: 1000
  enabledPlugins:
    - rabbitmq_shovel
    - rabbitmq_federation
backupDaemon:
  install: true
  backupStorage:
    storageClass: {applicable_to_env_storage_class}
    size: 10Gi
  securityContext:
    runAsUser: 1000
```

### DR Scheme

The minimal template for DR scheme is as follows.

```yaml
name: rabbitmq-service

disasterRecovery:
  mode: "active"
  region: "north-america"

rabbitmq:
  auto_reboot: true
  hostpath_configuration: false
  custom_params:
    rabbitmq_vm_memory_high_watermark: 80%
    rabbitmq_default_user: admin
    rabbitmq_default_password: admin
  replicas: 3
  resources:
    requests:
      cpu: '1'
      memory: 2Gi
    limits:
      cpu: '1'
      memory: 2Gi
    storage: 499Mi
    storageclass: {applicable_to_env_storage_class}
  securityContext:
    fsGroup: 1000
    runAsUser: 1000
  enabledPlugins:
    - rabbitmq_shovel
    - rabbitmq_federation
backupDaemon:
  install: true
  backupStorage:
    storageClass: {applicable_to_env_storage_class}
    size: 10Gi
  securityContext:
    runAsUser: 1000
```

For more information, refer to the [RabbitMQ Disaster Recovery](/docs/public/disasterRecovery.md) section in _Cloud Platform Disaster Recovery Guide_.

## Google Cloud Examples

### HA Scheme

<details>
<summary>Click to expand YAML</summary>

```yaml
name: rabbitmq-service

rabbitmq:
  auto_reboot: true
  hostpath_configuration: false
  custom_params:
    rabbitmq_vm_memory_high_watermark: 80%
    rabbitmq_default_user: admin
    rabbitmq_default_password: admin
  replicas: 3
  resources:
    requests:
      cpu: '1'
      memory: 2Gi
    limits:
      cpu: '1'
      memory: 2Gi
    storage: 499Mi
    storageclass: {applicable_to_env_storage_class}
  securityContext:
    fsGroup: 1000
    runAsUser: 1000
  enabledPlugins:
    - rabbitmq_shovel
    - rabbitmq_federation
backupDaemon:
  enabled: true
  backupSchedule: "*/15 * * * *"
  evictionPolicy: "1h/1d,7d/delete"
  persistentVolume: null
  s3:
    enabled: true
    url: "https://storage.googleapis.com"
    bucket: "rabbitmqbucket"
    keyId: "s3keyid"
    keySecret: "s3keysecret"
```

</details>

### DR Scheme

<details>
<summary>Click to expand YAML</summary>

```yaml
name: rabbitmq-service

disasterRecovery:
  mode: "active"
  region: "north-america"

rabbitmq:
  securityContext:
    fsGroup: 1000
    runAsUser: 1000
  auto_reboot: true
  hostpath_configuration: false
  custom_params:
    rabbitmq_vm_memory_high_watermark: 80%
    rabbitmq_default_user: admin
    rabbitmq_default_password: admin
  replicas: 3
  resources:
    requests:
      cpu: '1'
      memory: 2Gi
    limits:
      cpu: '1'
      memory: 2Gi
    storage: 499Mi
    storageclass: {applicable_to_env_storage_class}
  enabledPlugins:
    - rabbitmq_shovel
    - rabbitmq_federation
backupDaemon:
  enabled: true
  backupSchedule: "*/15 * * * *"
  evictionPolicy: "1h/1d,7d/delete"
  persistentVolume: null
  s3:
    enabled: true
    url: "https://storage.googleapis.com"
    bucket: "rabbitmqbucket"
    keyId: "s3keyid"
    keySecret: "s3keysecret"
```

For more information, refer to the [RabbitMQ Disaster Recovery](/docs/public/disasterRecovery.md) section in _Cloud Platform Disaster Recovery Guide_.

</details>

## AWS Examples

### External Scheme

<details>
<summary>Click to expand YAML</summary>

```yaml
externalRabbitmq:
  enabled: true
  url: https://vpc-amazon.mq.us-east-1.amazonaws.com
  username: admin
  password: admin
  replicas: 1
  clusterName: test-rabbitmq-01
telegraf:
  install: true
  metricCollectionInterval: 30s
backupDaemon:
  enabled: true
  s3:
    enabled: true
    url: https://s3.amazonaws.com
    bucket: rabbitmq-backup
    keyId: AKIA8Z7RN3SLODHHKA7Y
    keySecret: ZaROE3F0SvLT7jnSxbJ8XNh+fG0sZ8ze9aou3t6v
rabbitmqPrometheusMonitoring: false
```

</details>

### DR Scheme

Not applicable

## Azure Examples

### HA Scheme

The same as [On-Prem Examples HA Scheme](#on-prem-examples).

### DR Scheme

The same as [On-Prem Examples DR Scheme](#on-prem-examples).

# Upgrade

## Common

In general, the upgrade procedure is the same as the initial deployment.
Follow the Release Notes and Breaking Changes in the version you install to find the details.
If you upgrade to a version that has several major different changes from the installed version, for example, 0.3.1 over 0.1.1,
then check the Release Notes and Breaking Changes sections for `0.2.0` and `0.3.0` versions.

**Important**: Do not change the `rabbitmq.hostpath_configuration` parameter during the upgrade. Upgrade from a predefined PV to storage class is not supported, use reinstall instead.

## Scale In

Scale In (decreasing) replicas are not supported out of the box. You need to be sure that the removed nodes do not contain not-replicated unique data.

## Version Upgrade and Feature Flags

To upgrade RabbitMQ version you need to make sure that all feature flags not marked as experimental are enabled.

To check that, execute the following command in any RabbitMQ pod:

```text
  rabbitmqctl list_feature_flags
```

or check enabled feature flags in RabbitMQ UI.

To enable all necessary feature flags use the following command in any RabbitMQ pod:

```text
rabbitmqctl enable_feature_flag all
```

or enable flags on RabbitMQ UI.

Note: Starting from version 0.9.0, the enabling of feature flags is performed automatically during installation.

If you encounter problems with feature flags during RabbitMQ upgrade, roll back to the previous version and enable all necessary feature flags.

To upgrade RabbitMQ for more than one minor version it is necessary to make a consistent upgrade through all intermediate versions.
For example to upgrade from `3.10.x` to `3.12.x` you need to upgrade from `3.10.x` to `3.11.x` and after that to `3.12.x`.

## CRD Upgrade

Custom resource definition `RabbitMQService` should be upgraded before the installation if the new version has major
changes.
<!-- #GFCFilterMarkerStart# -->
The CRD for this version is stored in [crd.yaml](../../operator/charts/helm/rabbitmq/crds/crd.yaml) and can be
applied with the following command:

  ```sh
  kubectl replace -f crd.yaml
  ```

<!-- #GFCFilterMarkerEnd# -->
It can be done automatically during the upgrade with [Automatic CRD Upgrade](#automatic-crd-upgrade).

### Automatic CRD Upgrade

It is possible to upgrade CRD automatically on the environment to the latest one that is presented with the installing version.
This feature is enabled by default if the `DISABLE_CRD` parameter is not "true".

Automatic CRD upgrade requires the following cluster rights for the deployment user:

```yaml
- apiGroups: [ "apiextensions.k8s.io" ]
  resources: [ "customresourcedefinitions" ]
  verbs: [ "get", "create", "patch" ]
```

## Migration From DVM to Helm

To update RabbitMQ from DVM to Helm on an OpenShift environment, install the RabbitMQ service using Helm to a project with a non-Helm version.
All deployment secrets, users, roles, and role bindings are deleted automatically before the installation.
If the installation failed, or you need to delete the entities manually, implement the following steps:

1. Delete rabbitmq-default-secret and rabbitmq-monitoring secrets using the following commands:

   ```sh
   oc delete secret rabbitmq-default-secret
   oc delete secret rabbitmq-monitoring
   ```

2. Delete RabbitMQ serviceaccount, endpoint-reader, and secret-patcher-and-reader roles using the following commands:

   ```sh
   oc delete serviceaccount rabbitmq
   oc delete role endpoint-reader
   oc delete role secret-patcher-and-reader
   oc delete rolebinding secret-patcher-and-reader
   oc delete rolebinding endpoint-reader
   ```

3. Install RabbitMQ service using Helm to a project with a non-Helm version.

4. Restart all RabbitMQ pods after successful installation.

**Important**: It is recommended to not change the deployment parameters.

## HA to DR Scheme

For more information, refer to the [RabbitMQ Disaster Recovery](/docs/public/disasterRecovery.md) section in _Cloud Platform Disaster Recovery Guide_.

# Additional Features

## Multiple Availability Zone Deployment

When deploying to a cluster with several availability zones, it is important that RabbitMQ pods start in different
availability zones.

### Affinity

You can manage pods' distribution using `affinity` rules to prevent Kubernetes from running RabbitMQ pods on nodes of
the same availability zone.

**Note**: This section describes deployment only for `storage class` Persistent Volumes (PV) type because with
Predefined PV, the RabbitMQ pods are started on the nodes that are specified explicitly with Persistent Volumes. In
that way, it is necessary to take care of creating PVs on nodes belonging to different availability zones in advance.

#### Replicas Fewer Than Availability Zones

For cases when the number of RabbitMQ pods (value of the `rabbitmq.replicas` parameter) is equal or less than the number of
availability zones, you need to restrict the start of pods to one pod per availability zone.
You can also specify additional node affinity rules to start pods on allowed Kubernetes nodes.

For this, you can use the following affinity rules:

<details>
<summary>Click to expand YAML</summary>

```yaml
rabbitmq:
  affinity:
    podAntiAffinity: {
      "requiredDuringSchedulingIgnoredDuringExecution": [
        {
          "labelSelector": {
            "matchExpressions": [
              {
                "key": "app",
                "operator": "In",
                "values": [
                  "rmqlocal"
                ]
              }
            ]
          },
          "topologyKey": "topology.kubernetes.io/zone"
        }
      ]
    }
    nodeAffinity: {
      "requiredDuringSchedulingIgnoredDuringExecution": {
        "nodeSelectorTerms": [
          {
            "matchExpressions": [
              {
                "key": "role",
                "operator": "In",
                "values": [
                  "compute"
                ]
              }
            ]
          }
        ]
      }
    }
```

</details>

Where:

* `topology.kubernetes.io/zone` is the name of the label that defines the availability zone. This is the default name for Kubernetes
  1.17+. Earlier, `failure-domain.beta.kubernetes.io/zone` was used.
* `role` and `compute` are the sample name and value of the label that defines the region to run RabbitMQ pods.

#### Replicas More Than Availability Zones

For cases when the number of RabbitMQ pods (value of the `rabbitmq.replicas` parameter) is greater than the number of availability
zones, you need to restrict the start of pods to one pod per node and specify the preferred rule to start on different
availability zones.
You can also specify an additional node affinity rule to start the pods on allowed Kubernetes nodes.

For this, you can use the following affinity rules:

<details>
<summary>Click to expand YAML</summary>

```yaml
rabbitmq:
  affinity:
    podAntiAffinity: {
      "requiredDuringSchedulingIgnoredDuringExecution": [
        {
          "labelSelector": {
            "matchExpressions": [
              {
                "key": "app",
                "operator": "In",
                "values": [
                  "rmqlocal"
                ]
              }
            ]
          },
          "topologyKey": "kubernetes.io/hostname"
        }
      ],
      "preferredDuringSchedulingIgnoredDuringExecution": [
        {
          "weight": 100,
          "podAffinityTerm": {
            "labelSelector": {
              "matchExpressions": [
                {
                  "key": "app",
                  "operator": "In",
                  "values": [
                    "rmqlocal"
                  ]
                }
              ]
            },
            "topologyKey": "topology.kubernetes.io/zone"
          }
        }
      ]
    }
    nodeAffinity: {
      "requiredDuringSchedulingIgnoredDuringExecution": {
        "nodeSelectorTerms": [
          {
            "matchExpressions": [
              {
                "key": "role",
                "operator": "In",
                "values": [
                  "compute"
                ]
              }
            ]
          }
        ]
      }
    }
```

</details>

Where:

* `kubernetes.io/hostname` is the name of the label that defines the Kubernetes node. This is the standard name for Kubernetes.
* `topology.kubernetes.io/zone` is the name of the label that defines the availability zone. This is the standard name for
  Kubernetes 1.17+. Earlier, `failure-domain.beta.kubernetes.io/zone` was used.
* `role` and `compute` are the sample name and value of the label that defines the region to run RabbitMQ pods.

# Deployment With Managed External RabbitMQ

RabbitMQ allows you to deploy RabbitMQ side services (Monitoring) without deploying RabbitMQ, using an external URL.
To enable it, disable deploying RabbitMQ with `externalRabbitmq.enabled|: true` and fill the following parameters:
`externalRabbitmq.url`, `externalRabbitmq.username`, `externalRabbitmq.password`, `externalRabbitmq.replicas` and `externalRabbitmq.clusterName`.
You can find the descriptions in the [Parameters](#parameters) section.

## AmazonMQ in AWS

RabbitMQ chart allows you to deploy Backup Daemon or Monitoring with AmazonMQ cluster in AWS.

The process of deployment to Amazon Kubernetes Cluster does not differ from the usual deployment to Kubernetes, but AmazonMQ can be used instead of platform's RabbitMQ.

For examples and details, refer to the [Deploying Side Services Using AmazonMQ](/docs/public/managed/amazon/README.md) section.

# Queue Recommendations

For HA scenarios we recommend to use [Quorum Queues](https://www.rabbitmq.com/docs/quorum-queues).

[Classic Queues](https://www.rabbitmq.com/docs/classic-queues) are recommended for non HA scenarios.

For advanced queues management RabbitMQ provides queues [TTL](https://www.rabbitmq.com/docs/ttl#queue-ttl-using-x-args)
and [Queue Length Limit](https://www.rabbitmq.com/docs/maxlength) options. For temporary queues we recommend to set TTL
timer or auto delete property depending on the expected queue downtime.
It is also possible to set [TTL for messages](https://www.rabbitmq.com/docs/ttl#per-queue-message-ttl) in queue.

# Frequently Asked Questions

## What to Do if a Kubernetes Version is Upgraded Before Application?

It is important to upgrade the application to a certified version until a Kubernetes upgrade.

If you already face the issue, you have to delete all Helm specific secrets (for example, `sh.helm.release.v1.rabbitmq-service-rabbitmq-service.v1`) from the namespace.

For example:

```bash
kubectl get secret -l "owner=helm"

kubectl delete secret -l "owner=helm"
```

Then install a new version.

## Deployer Job Failed With Status Check but Application Works Fine

It can be an issue with getting the status from the RabbitMQ operator. You need to get operator logs and statuses from the RabbitMQ custom
resource and analyze them.

For example:

```bash
kubect get rabbitmqservices rabbitmq -o yaml
```

## Deployer Job Failed With Unknown Fields in Rabbitmqservices.qubership.org

It can be an issue with CRD changes. Refer to [CRD Upgrade](#crd-upgrade) for details.

## Deployer Job Failed With an Error in Templates

Make sure you performed the necessary [Prerequisites](#prerequisites). Fill the [Parameters](#parameters) correctly and compare
with [Examples](#on-prem-examples).

## Deployer Job Fails and Operator Contains "Forbidden: updates to statefulset spec for fields..." Error

The following error in the operator specifies that you have changed the parameters that can not be updated in `StatefulSet`.

```text
[2023-08-16 13:34:52,561] kopf.objects         [ERROR   ] [platform-rabbitmq/rabbitmq-service] Handler 'on_update' failed with an exception. Will retry.
Traceback (most recent call last):
  File "/usr/local/lib/python3.7/site-packages/kopf/_core/actions/execution.py", line 285, in execute_handler_once
    subrefs=subrefs,
  File "/usr/local/lib/python3.7/site-packages/kopf/_core/actions/execution.py", line 379, in invoke_handler
    runtime=runtime,
  File "/usr/local/lib/python3.7/site-packages/kopf/_core/actions/invocation.py", line 139, in invoke
    await asyncio.shield(future)  # slightly expensive: creates tasks
  File "/usr/local/lib/python3.7/concurrent/futures/thread.py", line 57, in run
    result = self.fn(*self.args, **self.kwargs)
  File "/opt/operator/handler.py", line 1400, in on_update
    kub_helper.update_config()
  File "/opt/operator/handler.py", line 989, in update_config
    self.update_stateful_set("rmqlocal")
  File "/opt/operator/handler.py", line 387, in update_stateful_set
    self._apps_v1_api.replace_namespaced_stateful_set(name, self._workspace, statefulsetbody)
  File "/usr/local/lib/python3.7/site-packages/kubernetes/client/api/apps_v1_api.py", line 8848, in replace_namespaced_stateful_set
    return self.replace_namespaced_stateful_set_with_http_info(name, namespace, body, **kwargs)  # noqa: E501
  File "/usr/local/lib/python3.7/site-packages/kubernetes/client/api/apps_v1_api.py", line 8965, in replace_namespaced_stateful_set_with_http_info
    collection_formats=collection_formats)
  File "/usr/local/lib/python3.7/site-packages/kubernetes/client/api_client.py", line 353, in call_api
    _preload_content, _request_timeout, _host)
  File "/usr/local/lib/python3.7/site-packages/kubernetes/client/api_client.py", line 184, in __call_api
    _request_timeout=_request_timeout)
  File "/usr/local/lib/python3.7/site-packages/kubernetes/client/api_client.py", line 405, in request
    body=body)
  File "/usr/local/lib/python3.7/site-packages/kubernetes/client/rest.py", line 291, in PUT
    body=body)
  File "/usr/local/lib/python3.7/site-packages/kubernetes/client/rest.py", line 234, in request
    raise ApiException(http_resp=r)
kubernetes.client.exceptions.ApiException: (422)
Reason: Unprocessable Entity
HTTP response headers: HTTPHeaderDict({'Audit-Id': 'ade1b955-f9fd-47b8-9ce4-73a4c748a6bd', 'Cache-Control': 'no-cache, private', 'Content-Type': 'application/json', 'X-Kubernetes-Pf-Flowschema-Uid': '7864e097-2ca5-48ca-b152-3a26dc8dd055', 'X-Kubernetes-Pf-Prioritylevel-Uid': '0b84b987-ffd3-4222-a927-f35069935b66', 'Date': 'Wed, 16 Aug 2023 13:34:52 GMT', 'Content-Length': '676'})
HTTP response body: {"kind":"Status","apiVersion":"v1","metadata":{},"status":"Failure","message":"StatefulSet.apps \"rmqlocal\" is invalid: spec: Forbidden: updates to statefulset spec for fields other than 'replicas', 'ordinals', 'template', 'updateStrategy', 'persistentVolumeClaimRetentionPolicy' and 'minReadySeconds' are forbidden","reason":"Invalid","details":{"name":"rmqlocal","group":"apps","kind":"StatefulSet","causes":[{"reason":"FieldValueForbidden","message":"Forbidden: updates to statefulset spec for fields other than 'replicas', 'ordinals', 'template', 'updateStrategy', 'persistentVolumeClaimRetentionPolicy' and 'minReadySeconds' are forbidden","field":"spec"}]},"code":422}
```

Most often it is associated with persistent volumes' configuration. To determine the problem area, in OpenShift/Kubernetes, find the `StatefulSet` configuration using the following command:

```sh
kubectl describe statefulset rmqlocal -n <namespace_name>
```

Pay attention to the `Volume Claims` section and compare its values to the persistence parameters (`rabbitmq.resources.storage`, `rabbitmq.resources.storageclass`) specified in the Deployer job.

```yaml
Volume Claims:
  Name:          default-vct-name
  StorageClass:  local-path
  Labels:        <none>
  Annotations:   volume.beta.kubernetes.io/storage-class=local-path
  Capacity:      750Mi
  Access Modes:  [ReadWriteOnce]
```

There are two ways to solve the problem:

1. In the Deployer job, use the same values specified in the `StatefulSet` configuration.
2. Remove the `StatefulSet` resource without deleting the pods:

   ```sh
   kubectl delete sts rmqlocal -n <namespace_name> --cascade=orphan
   ```

   Run the Deployer job with the required parameters and `upgrade` mode.
