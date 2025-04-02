You can deploy RabbitMQ using an operator. For this deployment, only the storage class and local PV configurations are supported. Overall, the RabbitMQ configuration is similar to the RabbitMQ deployment with OpenShift deployer, except the OpenShift route is not created when deploying with the operator.

To deploy RabbitMQ with an operator in OpenShift/Kubernetes:

1. Download the following operator deploy directory, [https://git.qubership.org/THIRDPARTY.Platform.Services/RabbitMQ/tree/rabbitmq-operator/operator/deploy](https://git.qubership.org/THIRDPARTY.Platform.Services/RabbitMQ/tree/rabbitmq-operator/operator/deploy).
1. Replace the `REPLACE_IMAGE` value in the **/deploy/operator.yaml** file with the required operator image. You can replace the image using the following command:
   
   ```
   sed -i 's|REPLACE_IMAGE|artifactorycn.qubership.org:17008/thirdparty/thirdparty.platform.services_rabbitmq:rabbitmq-operator_latest_operator|g' deploy/operator.yaml
   ``` 
   
   You can also specify the `LOGLEVEL` environment variable in order to set the logging level of the operator in the **/deploy/operator.yaml** file. Another available environment variable is `OPERATOR_DELETE_RESOURCES`, which specifies whether the operator should delete all RabbitMQ resources when the RabbitMQ Custom Resource (CR) is deleted. When not specified, the value is `False`. **Warning:** If `OPERATOR_DELETE_RESOURCES` is set to `True`, the RabbitMQ operator must be up and running when you are deleting the CR. Otherwise, the delete operation may be stuck for an extended period of time, and may stop you from deleting the namespace. 
1. Set the required RabbitMQ configuration in the **/deploy/cr.yaml** file. For more information, refer to [Configuration](#configuration).
1. Create a RabbitMQ secret in the project/namespace. You can use the following command:

   ```oc create secret generic rabbitmq-default-secret --from-literal=user="${RABBITMQ_USER}" --from-literal=password="${RABBITMQ_PASSWORD}" --from-literal=rmqcookie="${RABBITMQ_COOKIE}"```
   
1. Apply the files from the **operator** directory using the following commands:

   ```
   kubectl apply -f deploy/role.yaml
   kubectl apply -f deploy/service_account.yaml
   kubectl apply -f deploy/role_binding.yaml
   kubectl apply -f deploy/crd.yaml
   kubectl apply -f deploy/operator.yaml
   ```

**Note**: To apply crd, ensure you have cluster-admin privileges.

When the operator pod is up and running, you can deploy RabbitMQ using the `kubectl apply -f /deploy/cr.yaml` command.

# Configuration

The list of configuration parameters is as follows:

* `spec.rabbitmq.dockerImage` - This parameter specifies the RabbitMQ image for the operator.
* `spec.rabbitmq.auto_reboot` - This parameter specifies the RabbitMQ upgrade. If set to `true`, the RabbitMQ pods are rebooted one after another during update and it checks the cluster formation.
* `spec.rabbitmq.hostpath_configuration` - This parameter specifies whether local PVs are to be used. If set to `true`, RabbitMQ tries to deploy on local PVs using the PVs and nodes provided in other parameters. If set to `false`, RabbitMQ is deployed using the storage class.
* `spec.rabbitmq.custom_params.rabbitmq_vm_memory_high_watermark` - This parameter specifies the RabbitMQ vm_memory_high_watermark. This parameter sets the RabitMQ memory as a percentage of the maximum available memory in a pod. For more information about the `vm_memory_high_watermark` parameter, refer to the official RabbitMQ documentation at [https://www.rabbitmq.com/memory.html](https://www.rabbitmq.com/memory.html).
* `spec.rabbitmq.volumes` - This parameter specifies the RabbitMQ PVs to be used for local PV installation only.
* `spec.rabbitmq.nodes` - This parameter specifies the nodes where RabbitMQ PVs are located for local PV installation only.
* `spec.rabbitmq.dockerImage` - This parameter specifies the RabbitMQ image for the operator.
* `spec.rabbitmq.replicas` - This parameter specifies the RabbitMQ replicas.
* `spec.rabbitmq.resources.limits` - This parameter specifies the RabbitMQ CPU/memory limits.
* `spec.rabbitmq.resources.requests` - This parameter specifies the RabbitMQ CPU/memory requests.
* `spec.rabbitmq.resources.storage` - This parameter specifies the RabbitMQ storage size.
* `spec.rabbitmq.resources.storageclass` - This parameter specifies the RabbitMQ storage class. When used for deployment on local PVs, it must be the same as what is set on PVs. When the storage class is not set, use ''.
* `spec.rabbitmq.enabledPlugins` - This parameter specifies the RabbitMQ enabled plugins.
* `spec.rabbitmq.fsGroup` - This parameter specifies the configuration of the security context for a pod.
* `spec.rabbitmq.runAsUser` - This parameter specifies user IDs to run processes in a pod.
* `spec.rabbitmq.podAntiAffinity` - This parameter specifies the affinity rules for RabbitMQ. It works only for storage class configuration.
* `spec.rabbitmq.secret_change` - This parameter must be updated when the password in the RabbitMQ secret is manually changed.

# Upgrade

RabbitMQ can be upgraded with the operator. However, similar to the Deploy job, you cannot upgrade the storage type, class, and PVs, and you need to reinstall RabbitMQ. By default, the operator updates statefulsets without restarting the pods, so for the changes to take place, you must restart the pods manually. Alternatively, you can use the `spec.rabbitmq.auto_reboot` parameter, which works similarly to the `AUTO_REBOOT` job deploy parameter. When updating the RabbitMQ default password, firstly, change the secret with the password, and after that change the `spec.rabbitmq.secret_change` parameter in the CR. The `spec.rabbitmq.auto_reboot` parameter must be set to `true` during password update.