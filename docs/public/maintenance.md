This section provides information about RabbitMQ maintenance issues and describes the RabbitMQ monitoring metrics.

# Change RabbitMQ Default Password

To change default user, you can run the upgrade job with new parameters and the parameter `rabbitmq.auto_reboot=true`.
Also, you can change the default user password that was set during deployment manually.

To change the user password, you can use operator and manual secret change.

To change the password in rabbitmq-default-secret, you need to hash new password with base64 hash and use upgrade with new value for rabbitmq.secret_change parameter.
Alternatively, you can change the default password from the terminal of any RabbitMQ pod using the `change_password` command. For example:

```text
change_password default_user_name new_password
```

Where,

* `default_user_name` is the name of the default user that was set when the service was deployed.
* `new_password` is the new password for the default user.

**Note**: If you have a RabbitMQ monitoring pod in your project, you need to restart the pod after executing the script.

You should use the above command only for the default user.

For other users, use the RabbitMQ Management UI or the following command in the pod's terminal:

```text
rabbitmqctl change_password user_name new_password
```

# Change RabbitMQ Username and Password

In RabbitMQ existing username could not be changed, so you need to create new user with the same grants and delete previous user.
If RabbitMQ UI is available, follow the next steps:

  1. Open RabbitMQ management UI, go to `Admin` page and choose `Users` from the menu on the right side
  2. Create new user
  3. Choose new user from the list and click on it
  4. Add desired vhost permissions and tags for the new user, then click `Update user` button
  5. Choose old user from the list, click on it and press `Delete this user`

Same steps could be performed from RabbitMQ pod with `rabbitmqctl`:

  1. Use `rabbitmqctl add_user` command to create new user ([link](https://www.rabbitmq.com/rabbitmqctl.8.html#add_user))
  2. Use `rabbitmqctl set_user_tags` command to add desired tags to user ([link](https://www.rabbitmq.com/rabbitmqctl.8.html#set_user_tags))
  3. Use `rabbitmqctl set_permissions` command to add permissions for vhost to user ([link](https://www.rabbitmq.com/rabbitmqctl.8.html#set_permissions))
  4. Use `rabbitmqctl delete_user` command to delete old user ([link](https://www.rabbitmq.com/rabbitmqctl.8.html#delete_user))

**Important** If you want to change default user password, use [Change RabbitMQ Default Password](#change-rabbitmq-default-password) article.
If you want to change default username, you must add `admin` tag and `.*.*.*` permissions for `/` vhost for the new default user.
Then you need to manually update `rabbitmq-default-secret` with new username and password and restart all pods that use default user before deleting old default user.

# Change Parameters of the Monitoring Pod

The monitoring parameters, such as `influxdb connection parameters` and `metric-collection-interval`, are stored in the secret `rabbitmq-monitoring`. To modify these parameters, update the secret.
After you update the secret, restart the monitoring pod.

# Change the Number of Running Pods or Configuration

To change number of RabbiMQ pods or RabbitMQ configuration, refer to the **[Upgrade](installation.md#upgrade)** section in the _RabbitMQ Operator Installation Procedure_.

# Backup and Recovery

This section describes the backup and recovery procedures for RabbitMQ in detail.

## Definitions

You can backup RabbitMQ queues, users, and vhosts and restore them by exporting or importing definitions.
For more information about backup and restore, refer to the _Official RabbitMQ Documentation_ at [https://www.rabbitmq.com/backup.html](https://www.rabbitmq.com/backup.html).

## Backup Definitions with rabbitmq-backup-daemon

This section provides information about backup and recovery procedures using API for RabbitMQ Service.

### Backup

You can back up data for RabbitMQ Service per your requirement. You can select any one of the following options for backup:

* Full manual backup
* Granular backup
* Not Evictable Backup

### Full Manual Backup

To back up definitions of all RabbitMQ vhosts, run the following command:

```sh
curl -XPOST http://localhost:8080/backup
```

After executing the command, you receive a name of the folder where the backup is stored. For example, `20190321T080000`.

### Granular Backup

To back up definition for specified vhost, you can specify them in the `dbs` parameter. For example:

```sh
curl -XPOST -v -H "Content-Type: application/json" -d '{"dbs":["vhost1","vhost2"]}'  http://localhost:8080/backup
```

### Not Evictable Backup

If you do not want the backup to be evicted automatically, you need to add the `allow_eviction` property
with value as `False` in the request body. For example:

```sh
curl -XPOST -v -H "Content-Type: application/json" -d '{"allow_eviction":"False"}' http://localhost:8080/backup
```

### Backup Eviction by ID

To remove a specific backup, run the following command:

```sh
curl -XPOST http://localhost:8080/evict/<backup_id>
```

where `backup_id` is the name of specific backup to be evicted, for example, `20190321T080000`.
If the operation is successful, the following text displays: `Backup <backup_id> successfully removed`.

### Backup Status

When the backup is in progress, you can check its status using the following command:

```sh
curl -XGET http://localhost:8080/jobstatus/<backup_id>
```

where `backup_id` is the backup name received at the backup execution step. The result is JSON with
the following information:

* `status` - Status of operation. The possible options are:
  * Successful
  * Queued
  * Processing
  * Failed
* `message` - Description of error (optional field)
* `vault` - The name of vault used in recovery
* `type` - The type of operation. The possible options are:
  * backup
  * restore
* `err` - None if no error, last 5 lines of log if `status=Failed`
* `task_id` - The identifier of the task

### Backup Information

To get the backup information, use the following command:

```sh
curl -XGET http://localhost:8080/listbackups/<backup_id>
```

where `backup_id` is the name of specific backup. The command returns JSON string with data about
specific backup:

* `ts` - The UNIX timestamp of backup.
* `spent_time` - The time spent on backup (in ms)
* `db_list` - The list of stored vhosts (only for granular backup)
* `id` - The name of backup
* `size` - The size of backup in bytes
* `evictable` - Whether backup is evictable, _true_ if backup is evictable and _false_ otherwise
* `locked` - Whether backup is locked. _true_ if backup is locked (either process is not finished, or it failed somehow)
* `exit_code` - The exit code of backup script
* `failed` - Whether backup failed or not. _true_ if backup failed and _false_ otherwise
* `valid`- Backup is valid or not. _true_ if backup is valid and _false_ otherwise

### Recovery

To recover data from a specific backup, you need to specify JSON with information about a backup name (`vault`) or timestamp(`ts`, optional),
if vault parameter presented timestamp will be ignored, if timestamp presented backup with equal or newer timestamp will be restored.

You also can start a recovery with specifying vhosts (`dbs`). In this case only snapshots for specified vhosts is restored.

```sh
curl -u username:password -XPOST -v -H "Content-Type: application/json" -d '{"vault":"20190321T080000", "dbs":["vhost1","vhost2"]}' http://localhost:8080/restore
```

Example restore from backup with timestamp specified:

```sh
curl -u username:password -XPOST -v -H "Content-Type: application/json" -d  '{"ts":"1689762600000"}' http://localhost:8080/restore
```

As a response, you receive `task_id`, which can be used to check _Recovery Status_.

### Recovery Status

When the recovery is in progress, you can check its status using the following command:

```sh
curl -XGET http://localhost:8080/jobstatus/<task_id>
```

where `task_id` is task ID received at the recovery execution step.

### Backups List

To receive list of collected backups, use the following command:

```sh
curl -XGET http://localhost:8080/listbackups
```

It returns JSON with list of backup names.

### Find Backup

To find the backup with timestamp equal or newer than specified, use the following command:

For full backups:

```sh
curl -XGET -u username:password -v -H "Content-Type: application/json" -d  '{"ts":"1689762600000"}' localhost:8080/find
```

For incremental backups:

```sh
curl -XGET -u username:password -v -H "Content-Type: application/json" -d  '{"ts":"1689762600000"}' localhost:8080/icremental/find
```

This command will return a JSON string with stats about particular backup or the first backup newer that specified timestamp:

* `ts`: UNIX timestamp of backup
* `spent_time`: time spent on backup (in ms)
* `db_list`: List of backed up databases
* `id`: vault name
* `size`: Size of backup in bytes
* `evictable`: whether backup is evictable
* `locked`: whether backup is locked (either process isn't finished, or it failed somehow)
* `exit_code`: exit code of backup script
* `failed`: whether backup failed or not
* `valid`: is backup valid or not
* `is_granular`: Whether the backup is granular
* `sharded`: Whether the backup is sharded
* `custom_vars`: Custom variables with values that were used in backup preparation. It is specified if `.custom_vars` file exists in backup

An example is given below:

```json
{"is_granular": false, "db_list": "full backup", "id": "20220113T230000", "failed": false, "locked": false, "sharded": false, "ts": 1642114800000, "exit_code": 0, "spent_time": "9312ms", "size": "25283b", "valid": true, "evictable": true, "custom_vars": {"mode": "hierarchical"}}
```

### Backup Daemon Health

To know the state of Backup Daemon, use the following command:

```sh
curl -XGET http://localhost:8080/health
```

You receive JSON with the following information:

```text
"status": status of backup daemon   
"backup_queue_size": backup daemon queue size (if > 0 then there are 1 or tasks waiting for execution)
 "storage": storage info:
  "total_space": total storage space in bytes
  "dump_count": number of backup
  "free_space": free space left in bytes
  "size": used space in bytes
  "total_inodes": total number of inodes on storage
  "free_inodes": free number of inodes on storage
  "used_inodes": used number of inodes on storage
  "last": last backup metrics
    "metrics['exit_code']": exit code of script 
    "metrics['exception']": python exception if backup failed
    "metrics['spent_time']": spent time
    "metrics['size']": backup size in bytes
    "failed": is failed or not
    "locked": is locked or not
    "id": vault name of backup
    "ts": timestamp of backup  
  "lastSuccessful": last successfull backup metrics
    "metrics['exit_code']": exit code of script 
    "metrics['spent_time']": spent time
    "metrics['size']": backup size in bytes
    "failed": is failed or not
    "locked": is locked or not
    "id": vault name of backup
    "ts": timestamp of backup
```

## Messages

For backing up messages, refer to the Official -RabbitMQ documentation_ at [https://www.rabbitmq.com/backup.html#messages-backup](https://www.rabbitmq.com/backup.html#messages-backup).
In OpenShift, to back up messages, you have to create copies of the Mnesia directories of each node.
Backing up the Mnesia directory only works if your pod name during the restore process is the same as it was during the backup process.
Currently, all RabbitMQ deployment options have the same pod names, except for the new `Host bound PVs` option that supports multi-node RabbitMQ with host bound PVs.
For this reason, the `Host bound PVs` option does not currently support a restore messages procedure from other deployment types,
including the old `One-Node-Local-PV` deployment option and vice versa.
The Mnesia directory is located at **/var/lib/rabbitmq/mnesia**.

To back up Mnesia directories in a cluster:

1. Stop the RabbitMQ service on the first RabbitMQ pod using the following terminal command:

   ```sh
   rabbitmqctl stop_app
   ```

2. Create a **/tmp/BACKUP_FLAG_FILE** file in the first RabbitMQ pod. It stops the RabbitMQ liveness/readiness probes from failing when the RabbitMQ has stopped to take a backup.
3. Repeat the Steps 1 and 2 for other RabbitMQ pods (pods named `rmqlocal-*`).
4. Back up **mnesia** folders on each RabbitMQ pod.
   For example, it is possible to download **mnesia** from pod 0 to a **backup_folder0** using the following command: `oc rsync rmqlocal-0:/var/lib/rabbitmq/mnesia backup_folder0`.
   When you have direct access to the RabbitMQ PVs, you can find the **mnesia** folder at **/PATH_TO_RABBITMQ_PV/mnesia**.
5. Start RabbitMQ service on each RabbitMQ pod using the following command: `rabbitmqctl start_app`.
   Starting RabbitMQ on one pod might require RabbitMQ running on another pod, so it is important not to wait for successful command completion before starting RabbitMQ on another pod.
6. Remove **/tmp/BACKUP_FLAG_FILE** from the pods.

To restore from a backup:

1. Deploy RabbitMQ with clean install option with the same number of replicas and the same pod names.
2. Stop RabbitMQ service on each RabbitMQ pod with the terminal command `rabbitmqctl stop_app`.
3. Create **/tmp/BACKUP_FLAG_FILE** in each RabbitMQ pod.
4. Remove **mnesia** folders in each RabbitMQ pod.
5. Copy all **mnesia** folders that were backed up on the corresponding pods.
   For example, to copy the **mnesia** folder from **backup_folder0** that was previously backed up, use the following command: `oc rsync backup_folder0\mnesia rmqlocal-0:/var/lib/rabbitmq`.
   When you have direct access to the RabbitMQ PVs, **mnesia** folder must be copied to **/PATH_TO_RABBITMQ_PV/mesia** folder on the corresponding PV.
6. Change permissions for **mnesia** folders using the following command on each pod: `chmod 777 -R var/lib/rabbitmq/mnesia`.
7. Start RabbitMQ service on each RabbitMQ pod using the following command: `rabbitmqctl start_app`.
   Starting RabbitMQ on one pod might require RabbitMQ running on another pod, so it is important not to wait for successful command completion before starting RabbitMQ on another pod.
8. Remove **/tmp/BACKUP_FLAG_FILE** from the pods.

# Robot Tests

Robot-tests, which are included in RabbitMQ manifest, can be used to validate RabbitMQ deployment.
For more information, refer to **[Running Robot Tests](installation.md#tests)** section in the _RabbitMQ Operator Installation Procedure_.

# List of Service Ports and Dependencies

RabbitMQ has the following different services:

* RabbitMQ service that is intended to be contacted by other microservices. This service is usually named `rabbitmq`. This service should be contacted by other applications to access RabbitMQ.
* RabbitMQ local service or services, usually named rmqlocal or rmqlocal-[SERVICE_NUMBER], should not be contacted by other applications, but they are still needed for RabbitMQ pods
  to contact each other. These services have the same ports as RabbitMQ service, and some additional internal ports.

External ports are ports that are present in RabbitMQ service or RabbitMQ-backup-daemon service:

* `5672` - Client-access, used by AMQP 0-9-1 and 1.0 clients with and without TLS
* `15672` - External management plugin port (HTTP)
* `15692` - Prometheus plugin metrics (HTTP)
* `8080` - Backupper API port (HTTP)

Internal ports are ports that are present in RabbitMQ local service or services:

* `15671` - Management plugin SSL port
* `4369` - Epmd, a helper discovery daemon used by RabbitMQ nodes and CLI tools
* `5671` - Client-access, used by AMQP 0-9-1 and 1.0 clients without and with TLS
* `25672` - Rabbitmqctl CLI tool

Internal container ports are ports that are not present in services, but are present in the RabbitMQ containers:

* `443`, `8989` - Ports for internal use

External dependencies:

* Influx DB port - Custom port required for monitoring, usually `8086`.
* kubernetes.default.svc.cluster.local:443 - Required for cluster formation, only when local PVs are not used.
* ```https://"$KUBERNETES_SERVICE_HOST":"$KUBERNETES_SERVICE_PORT_HTTPS"```  - Required for changing the RabbitMQ default password with the `change_password` command.

**Note**: All ports use the TCP protocol.

# Problems with Restarting RabbitMQ Pods and Liveness Probe

Sometimes, RabbitMQ pods restart or fail liveness probe due to memory problems.
This can be caused by connections with a large number of channels (more than 500) that are created on the same node or insufficiently high memory limit for the current load.
**Important**: When the `rabbitmq_vm_memory_high_watermark` parameter is set to more than 80%,
the RabbitMQ monitoring and the kubernetes dashboard can display incorrect data on memory consumption by nodes.
To check the memory consumption for RabbitMQ nodes,
use the RabbitMQ management UI (overview->node stats->memory details) or execute the `rabbitmq-diagnostics memory_breakdown` command on the RabbitMQ pod.
If you see a high memory consumption, consider increasing the memory limit for the RabbitMQ pods. This may solve the problem.

# Monitoring

For more information about monitoring, refer to [RabbitMQ Operator Service Monitoring](monitoring.md) in _Cloud Platform Monitoring Guide_.

# Disaster Recovery

For more information about Disaster Recovery, refer to [RabbitMQ Disaster Recovery](disasterRecovery.md) in _Cloud Platform Disaster Recovery Guide_.
