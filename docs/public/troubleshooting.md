The following topics are covered in this chapter:

[[_TOC_]]

This section provides detailed troubleshooting procedures for the RabbitMQ cluster.

# Prometheus Alerts

## NoMetrics

### Description

RabbitMQ fails to provide metrics or Prometheus fails to gather it.

### Possible Causes

- RabbitMQ pod failures or unavailability.
- Prometheus monitoring is not working correctly.
- Prometheus and RabbitMQ don't have enough resources to gather metrics.
- RabbitMQ prometheus plugin is disabled.

### Impact

- No monitoring information about RabbitMQ.

### Actions for Investigation

1. Check the status of RabbitMQ pods and Prometheus
2. Check if RabbitMQ prometheus plugin is enabled.
3. Review logs for RabbitMQ pods for any errors or issues.
4. Verify resource utilization of RabbitMQ pods (CPU, memory).

### Recommended Actions to Resolve Issue

1. Restart or redeploy RabbitMQ pods if they are in a failed state.
2. Enable RabbitMQ prometheus plugin.

## ClusterError

### Description

There is something wrong with the RabbitMQ cluster. For example, there is more than one RabbitMQ cluster in RabbitMQ namespace.

### Possible Causes

- RabbitMQ cluster tears apart.
- More than one RabbitMQ is deployed to one namespace.

### Impact

- Complete unavailability of the RabbitMQ cluster or split-brain issue.

### Actions for Investigation

1. Check the status of RabbitMQ pods.
2. Review logs for RabbitMQ pods for any errors or issues.
3. Verify cluster state of RabbitMQ following [RabbitMQ clustering guide](https://www.rabbitmq.com/clustering.html).
4. Check that only one RabbitMQ cluster deployed to the namespace.

### Recommended Actions to Resolve Issue

1. Check the network connectivity to the RabbitMQ pods.
2. Try to fix cluster problem manually following [RabbitMQ clustering guide](https://www.rabbitmq.com/clustering.html).
3. Restart or redeploy all RabbitMQ pods at once.

## SomePodsAreNotWorking

### Description

Some RabbitMQ pods are not working.

### Possible Causes

- RabbitMQ application in some pods not working.
- RabbitMQ processes on the pods were stopped by the `rabbitmqctl stop_app` command.

### Impact

- Unavailability of some RabbitMQ cluster pods (can cause problems with queues).

### Actions for Investigation

1. Check the status of RabbitMQ pods.
2. Review logs for RabbitMQ pods for any errors or issues.
3. Verify cluster state of RabbitMQ following [RabbitMQ clustering guide](https://www.rabbitmq.com/clustering.html).

### Recommended Actions to Resolve Issue

1. Try to fix cluster problem manually following [RabbitMQ clustering guide](https://www.rabbitmq.com/clustering.html).
2. Restart or redeploy not working RabbitMQ pods.

## MemoryAlarm

### Description

One of RabbitMQ pods reaches memory high watermark.

### Possible Causes

- Insufficient memory resources allocated to RabbitMQ pods.

### Impact

- Potential out-of-memory errors and RabbitMQ cluster instability.
- Degraded performance of services used the RabbitMQ.

### Actions for Investigation

1. Monitor the Memory usage trends on RabbitMQ Monitoring dashboard.
2. Review RabbitMQ management UI for memory breakdown.

### Recommended Actions to Resolve Issue

1. Try to increase Memory request, Memory limit for appropriate RabbitMQ statefulset.
2. Scale up RabbitMQ cluster if needed.

## DiskAlarm

### Description

One of RabbitMQ pods reaches disk limit.

### Possible Causes

- There is not enough space in RabbitMQ persistence storage.

### Impact

- Potential out-of-disk-space errors and RabbitMQ cluster unavailability.

### Actions for Investigation

1. Monitor the Disk usage trends on RabbitMQ Monitoring dashboard.

### Recommended Actions to Resolve Issue

1. Consider increasing the capacity of RabbitMQ storage.
2. Try deleting persistence messages and queues from RabbitMQ to free some space.

# Troubleshooting Scenarios

## Dispositions

Before implement any advice from this troubleshooting guide please check that RabbitMQ Monitoring pod exists and is up.  

## Cluster Formation

If RabbitMQ with persistent storage does not form a cluster on the first startup, it is recommended to completely reinstall RabbitMQ.
Cluster formation procedure is performed only during the first startup. You can form a cluster manually without reinstalling with `rabbitmqctl`.
For more information, refer to the _Official RabbitMQ Documentation_ [https://www.rabbitmq.com/clustering.html](https://www.rabbitmq.com/clustering.html).

**Note**: When using RabbitMQ operator deployment, you can check the operator logs for cluster formation.

**Note**: Restarting or joining nodes will lose their data.

## RabbitMQ Does Not Have Enough Permissions to Form a Cluster

RabbitMQ needs special permissions to form a cluster that are granted during installation.
However, if for some reason RabbitMQ does not get these permissions or for non-persistent storage, these permissions were withdrawn at some point after installation,
the following error is displayed in the logs:

```text
...
2018-10-30 13:48:23.372 [info] <0.197.0> Failed to get nodes from k8s - {failed_connect,[{to_address,{"kubernetes.default.svc.cluster.local",443}},
{inet,[inet],nxdomain}]}
2018-10-30 13:48:23.373 [error] <0.196.0> CRASH REPORT Process <0.196.0> with 0 neighbours exited with reason: no case clause matching {error,"{failed_connect,[{to_address,{\"kubernetes.default.svc.cluster.local\",443}},\n {inet,[inet],nxdomain}]}"} in rabbit_mnesia:init_from_config/0 line 163 in application_master:init/4 line 134
...
```

In OpenShift, the permissions can be granted manually by executing the following command in the RabbitMQ project:

`oc adm policy add-role-to-user admin -z default`

## Queue Data Corruption

Queue data can be corrupted in two different ways: queue index corruption and queue message corruption.

### Queue Index Corruption

If the queue index is corrupted, the following error is displayed in the logs:

```text
...
init terminating in do_boot",{could_not_start,rabbit,{{badmatch,{error,{{{function_clause,[{rabbit_queue_index,parse_segment_entries,[
...
```

If the queue index is corrupted, then complete reinstallation of RabbitMQ is necessary.

### Queue Message Corruption

Most of the messages can be found in the folder by address with the following pattern:
**/var/lib/rabbitmq/mnesia/rabbit@rmqlocal-0.rmqlocal.ankorabbitstatefulset0.svc.cluster.local/msg_stores/vhosts/628WB79CIFDYO9LJI6DKMI09L/queues/91JEVSWD28ANBLAZ9HBXYRCGU**.
Their names look like `[№].idx`. The larger the number in the name, the later the file is created.
When the data in this folder is corrupted, the queues become unavailable, and an error can be found in the logs, but the pod still starts.

The error in this case is as follows:

```text
...
2018-05-11 08:11:58.822 [error] <0.389.0> ** Generic server <0.389.0> terminating
** Last message in was {init,{<0.373.0>,[[{segments,[{12,3392},{10,16384},{8,16384},{7,16384},{6,16384},{5,16384},{4,16384},{3,16384},{2,16384},{1,16384},{0,16384},{9,16384},{11,16384}]},{persistent_ref,<<188,122,137,195,207,181,95,123,91,25,104,185,180,25,71,200>>},{persistent_count,200000},{persistent_bytes,2400000}]]}}
** When Server state == {q,{amqqueue,{resource,<<"/">>,queue,<<"testq">>},true,true,none,[],<0.389.0>,[],[],[],undefined,undefined,[],undefined,stopped,0,[],<<"/">>,#{user => <<"testuser_1">>}},none,false,undefined,undefined,{state,{queue,[],[],0},{active,-576460717996235,1.0}},undefined,undefined,undefined,undefined,{state,fine,5000,undefined},{0,nil},undefined,undefined,undefined,{state,{dict,0,16,16,8,80,48,{[],[],[],[],[],[],[],[],[],[],[],[],[],[],[],[]},{{[],[],[],[],[],[],[],[],[],[],[],[],[],[],[],[]}}},delegate},undefined,undefined,undefined,undefined,'drop-head',0,0,running}
** Reason for termination == 
** {function_clause,[{rabbit_variable_queue,d,[{delta,16384,200000,0,212992}],[{file,"src/rabbit_variable_queue.erl"},{line,1182}]},{rabbit_variable_queue,maybe_deltas_to_betas,2,[{file,"src/rabbit_variable_queue.erl"},{line,2642}]},{rabbit_variable_queue,init,8,[{file,"src/rabbit_variable_queue.erl"},{line,1440}]},{rabbit_priority_queue,init,3,[{file,"src/rabbit_priority_queue.erl"},{line,148}]},{rabbit_amqqueue_process,init_it2,3,[{file,"src/rabbit_amqqueue_process.erl"},{line,207}]},{rabbit_amqqueue_process,handle_call,3,[{file,"src/rabbit_amqqueue_process.erl"},{line,1133}]},{gen_server2,handle_msg,2,[{file,"src/gen_server2.erl"},{line,1026}]},{proc_lib,init_p_do_apply,3,[{file,"proc_lib.erl"},{line,247}]}]}
2018-05-11 08:11:58.822 [error] <0.392.0> Restarting crashed queue 'testq' in vhost '/'.
2018-05-11 08:11:58.822 [error] <0.373.0> Queue <0.389.0> failed to initialise: {function_clause,[{rabbit_variable_queue,d,[{delta,16384,200000,0,212992}],[{file,"src/rabbit_variable_queue.erl"},{line,1182}]},{rabbit_variable_queue,maybe_deltas_to_betas,2,[{file,"src/rabbit_variable_queue.erl"},{line,2642}]},{rabbit_variable_queue,init,8,[{file,"src/rabbit_variable_queue.erl"},{line,1440}]},{rabbit_priority_queue,init,3,[{file,"src/rabbit_priority_queue.erl"},{line,148}]},{rabbit_amqqueue_process,init_it2,3,[{file,"src/rabbit_amqqueue_process.erl"},{line,207}]},{rabbit_amqqueue_process,handle_call,3,[{file,"src/rabbit_amqqueue_process.erl"},{line,1133}]},{gen_server2,handle_msg,2,[{file,"src/gen_server2.erl"},{line,1026}]},{proc_lib,init_p_do_apply,3,[{file,"proc_lib.erl"},{line,247}]}]}
2018-05-11 08:11:58.822 [error] <0.389.0> CRASH REPORT Process <0.389.0> with 0 neighbours exited with reason: no function clause matching rabbit_variable_queue:d({delta,16384,200000,0,212992}) line 1182 in gen_server2:terminate/3 line 1161
2018-05-11 08:11:58.822 [error] <0.388.0> Supervisor {<0.388.0>,rabbit_amqqueue_sup} had child rabbit_amqqueue started with rabbit_prequeue:start_link({amqqueue,{resource,<<"/">>,queue,<<"testq">>},true,true,none,[],<0.29202.1>,[],[],[],undefined,...}, recovery, <0.387.0>) at <0.389.0> exit with reason no function clause matching rabbit_variable_queue:d({delta,16384,200000,0,212992}) line 1182 in context child_terminated
...
```

In this case, the problem can be solved by deleting the old queues. This error does not always occur. Sometimes, the queues are still available, and some of the older messages can be recovered.

## Vhost is Down due to a Corrupted Recovery File

It is possible that a recovery file for vhost might become corrupted. RabbitMQ management panel shows that one of the RabbitMQ vhost is `down`.
In this case, the RabbitMQ log shows the following:

```text
Unable to connect to AMQP server on rabbitmq.rmqproject.svc.cluster.local:5672 after None tries: Connection.open: (541) INTERNAL_ERROR - access to vhost 'testvhost' refused for user 'testuser_1': vhost 'testvhost' is down: InternalError: Connection.open: (541) INTERNAL_ERROR - access to vhost 'testvhost' refused for user 'testuser_1': vhost 'testvhost' is down
```

Also, the `/var/log/rabbitmq/log/crash.log` shows the following error:

```text
exception error: {{badmatch,{error,{not_a_dets_file,"/var/lib/rabbitmq/mnesia/rabbit@rmqlocal-0.rmqlocal.rmqproject.svc.cluster.local/msg_stores/vhosts/5ps2ma3y6c7zvwfldgr4yt4gb/recovery.dets"}}},[{rabbit_recovery_terms,open_table,1,[{file,"src/rabbit_recovery_terms.erl"},{line,197}]},{rabbit_recovery_terms,init,1,[{file,"src/rabbit_recovery_terms.erl"},{line,177}]},{gen_server,init_it,2,[{file,"gen_server.erl"}
```

To fix this problem, remove the corrupted file. In the example above, the corrupted file is
`/var/lib/rabbitmq/mnesia/rabbit@rmqlocal-0.rmqlocal.rmqproject.svc.cluster.local/msg_stores/vhosts/5ps2ma3y6c7zvwfldgr4yt4gb/recovery.dets`.
Then restart the vhost via management plugin or using the `rabbitmqctl restart_vhost test` command.

## RabbitMQ Pod Outage

If one pod with PVC fails, it can be redeployed and it rejoins the cluster.
All the persistent messages that were published in the non-mirrored queues of the failed pod should be accessible after the pod redeployment.
Mirrored queues are accessible even during pod outage, and only the master node is changed.

If RabbitMQ is without PVC, then it rejoins the cluster after the outage, and the messages from queues with mirrors can still be consumed.
However, all persistent messages from non-mirrored queues on the failed pod are lost.

In this case, you might see the following error in the logs:

```text
[2020-06-11 04:50:36.844][error] <0.2956.2> ** Generic server rabbit_connection_tracking terminating 
** Last message in was {'$gen_cast',{connection_created,[{pid,<0.3150.2>},{protocol,{'Direct',{0,9,1}}},{host,unknown},{port,unknown},{name,<<"<rabbit@rmqlocal-2.rmqlocal.rabbitredeploy.svc.cluster.local.3.3150.2>">>},{peer_host,unknown},{peer_port,unknown},{user,<<"testuser_1">>},{vhost,<<"/">>},{client_properties,[]},{type,direct},{connected_at,1591851036830},{node,'rabbit@rmqlocal-2.rmqlocal.rabbitredeploy.svc.cluster.local'},{user_who_performed_action,<<"testuser_1">>}]}}
** When Server state == nostate
** Reason for termination ==
** {{aborted,{no_exists,['tracked_connection_on_node_rabbit@rmqlocal-2.rmqlocal.rabbitredeploy.svc.cluster.local',{'rabbit@rmqlocal-2.rmqlocal.rabbitredeploy.svc.cluster.local',<<"<rabbit@rmqlocal-2.rmqlocal.rabbitredeploy.svc.cluster.local.3.3150.2>">>}]}},[{mnesia,abort,1,[{file,"mnesia.erl"},{line,355}]},{rabbit_connection_tracking,register_connection,1,[{file,"src/rabbit_connection_tracking.erl"},{line,269}]},{rabbit_connection_tracking,handle_cast,2,[{file,"src/rabbit_connection_tracking.erl"},{line,79}]},{gen_server,try_dispatch,4,[{file,"gen_server.erl"},{line,637}]},{gen_server,handle_msg,6,[{file,"gen_server.erl"},{line,711}]},{proc_lib,init_p_do_apply,3,[{file,"proc_lib.erl"},{line,249}]}]}
[2020-06-11 04:50:36.845][error] <0.2956.2> CRASH REPORT Process rabbit_connection_tracking with 0 neighbours exited with reason: {aborted,{no_exists,['tracked_connection_on_node_rabbit@rmqlocal-2.rmqlocal.rabbitredeploy.svc.cluster.local',{'rabbit@rmqlocal-2.rmqlocal.rabbitredeploy.svc.cluster.local',<<"<rabbit@rmqlocal-2.rmqlocal.rabbitredeploy.svc.cluster.local.3.3150.2>">>}]}} in mnesia:abort/1 line 355
```

This error should not affect RabbitMQ behavior, however, to get rid of it you can downscale RabbitMQ to 0 pods.
Since in this case, the storage is not persistent, this leads to loss of all RabbitMQ data.

## RabbitMQ Process Failure

RabbitMQ fails in some time after starting with the following error:

```text
[2021-03-19 09:44:59.766][error] <0.518.0> ** Generic server rabbit_disk_monitor terminating  
** Last message in was update 
** When Server state == {state,"/var/lib/rabbitmq/mnesia/rabbit@rmqlocal-0.rmqlocal.maas-rabbitmq.svc.cluster.local",50000000,4640010240,100,10000,#Ref<0.3996838169.2750939137.24502>,false,true,10,120000} 
** Reason for termination == ** {{unparseable,[]},[{rabbit_disk_monitor,parse_free_unix,1,
```

The reason for process termination is lack of resources (CPU, Memory) to start the disk monitor process. You need to increase the resource limits to avoid the above error.

## Memory Limit Alarm

When the memory limit is reached, RabbitMQ stops receiving messages and an alarm is sent to the logs. For more information about these alarms, refer to the _Official RabbitMQ Documentation_,
"Memory Alarms" at [https://www.rabbitmq.com/memory.html](https://www.rabbitmq.com/memory.html). You need to free some memory to start sending messages again.
You can specify a memory limit as an installation parameter.

An example of the memory limit alarm is as follows:

```text
...
2018-05-10 14:33:24.931 [warning] <0.215.0> memory resource limit alarm set on node 'rabbit@rmqlocal-0.rmqlocal.ankorabbitstatefulset0.svc.cluster.local'.

**********************************************************
*** Publishers will be blocked until this alarm clears ***
**********************************************************
2018-05-10 14:33:28.935 [info] <0.217.0> vm_memory_high_watermark clear. Memory used:249847808 allowed:256901120
...
```

## Disk Limit Alarm

When the disk resource limit is reached, RabbitMQ stops receiving messages, and an alarm is sent to the logs.
For more information about this alarm, refer to the _Official RabbitMQ Documentation_, "Disk Alarms" at [https://www.rabbitmq.com/disk-alarms.html](https://www.rabbitmq.com/disk-alarms.html).
You need to free some disk memory to start sending the messages again.

An example of the disk limit alarm is as follows:

```text
...
2018-05-10 14:33:24.931 [warning] <0.215.0> disk resource limit alarm set on node 'rabbit@rmqlocal-0.rmqlocal.ankorabbitstatefulset0.svc.cluster.local'.

**********************************************************
*** Publishers will be blocked until this alarm clears ***
**********************************************************
...
```

If the pod is restarted without clearing the alarm, it is possible that RabbitMQ pod would not start and the error message would be different.
When troubleshooting failed pods, please check that RabbitMQ storage is available and has enough free space.

## Disk Failure on One Node

Different issues can occur when the disk fails. In some cases, the cluster may become unavailable to the client, if the client is connected to a node with a failed disk and if this node gets failed.
It is also possible that the node will not fail, but RabbitMQ works as if there is no free disk space. In some cases, all vhosts stop on the node with a failed disk after the node is brought back up.

To fix the problems, you need to:

1. Create a new PVC for the failed pod.
2. Remove the pod with the failed disk. Wait until it restarts and joins the cluster.
3. If the vhosts are stopped on the node, restart them (for example, via UI).

## Problems with .erlang.cookie

If RabbitMQ is run as non-root or has permission issues, it creates problems .erlang.cookie.

The following error message is displayed:

```text
warning: /var/lib/rabbitmq/.erlang.cookie contents do not match RABBITMQ_ERLANG_COOKIE
chmod: changing permissions of '/var/lib/rabbitmq/.erlang.cookie': Operation not permitted
```

or

```text
Cookie file /var/lib/rabbitmq/.erlang.cookie must be accessible by owner only
```

The possible reasons are:

* Permission change on a PV.
* Starting RabbitMQ as another user. For example, using different SCC.
* Installing RabbitMQ on a PV that was not properly cleaned after previous RabbitMQ installation with different permissions.

To fix the problems, you need to perform the following steps:

* Clean RabbitMQ PVs. This may cause RabbiMQ to lose all data on the node with PV.
* Fix permission issues.

**Note**: The `.erlang.cookie` file is immediately recreated by RabbitMQ process after the file is deleted.
If RabbitMQ is running under the wrong user, deleting the file leads to another `.erlang.cookie` file being created with the same permissions.
You need to stop RabbitMQ on the node with the PV first to prevent `.erlang.cookie` recreation with wrong permissions.

## badmatch,{error,einval} error on NFS Storage

When RabbitMQ is restarted or updated while using PV or PVCs with NFS storage, the following error may occur.

```text
Using Custom Entrypoint
Configs were copied to the /etc/rabbitmq folder.
List of files and directories inside the RabbitMQ data folder: config
mnesia
schema
started_at_least_once

BOOT FAILED
===========

Error description:
    rabbit:start_it/1 line 454
    rabbit:boot_error/2 line 861
    rabbit_lager:log_locations/0 line 61
    rabbit_lager:ensure_lager_configured/0 line 162
    rabbit_lager:lager_configured/0 line 170
    lager:list_all_sinks/0 line 317
    lager_config:get/2 line 71
    ets:lookup(lager_config, {'_global',handlers})
error:{badmatch,{error,einval}}
Log file(s) (may contain more information):
   <stdout>
```

In this case, the issue is usually on NFS side and should be fixed there.
The most common cause for this behavior is that NFS might not allow to write in the existing file before reading it from the same file.
Therefore, when you start RabbitMQ, execute the following command in the RabbitMQ pod terminal before the error occurs:

`du -a /var/lib/rabbitmq`

## Operator Contains "Object is being deleted: statefulsets.apps already exists..." Error

Issue Description:

This issue can be seen if you are trying to modify or create a resource but your user or service account doesn't have the right permissions.

Error Example:

```text
[2023-08-16 13:34:52,561] kopf.objects         [ERROR   ] [platform-rabbitmq/rabbitmq-service] Handler 'on_create' failed with an exception. Will retry.
Traceback (most recent call last):
  File "/usr/local/lib/python3.7/site-packages/kopf/_core/actions/execution.py", line 276, in execute_handler_once
    subrefs=subrefs,
  File "/usr/local/lib/python3.7/site-packages/kopf/_core/actions/execution.py", line 371, in invoke_handler
    runtime=runtime,
  File "/usr/local/lib/python3.7/site-packages/kopf/_core/actions/invocation.py", line 139, in invoke
    await asyncio.shield(future)  # slightly expensive: creates tasks
  File "/usr/local/lib/python3.7/concurrent/futures/thread.py", line 58, in run
    result = self.fn(*self.args, **self.kwargs)
  File "/opt/operator/handler.py", line 1426, in on_create
    kub_helper.update_config()
  File "/opt/operator/handler.py", line 1103, in update_config
    self.update_stateful_set("rmqlocal")
  ...
  File "/usr/local/lib/python3.10/site-packages/kubernetes/client/rest.py", line 275, in POST
   return self.request("POST", url,
  File "/usr/local/lib/python3.10/site-packages/kubernetes/client/rest.py", line 234, in request
    raise ApiException(http_resp=r)
kubernetes.client.exceptions.ApiException: (409)
Reason: Conflict
HTTP response headers: HTTPHeaderDict({'Audit-Id': 'ade1b955-f9fd-47b8-9ce4-73a4c748a6bd', 'Cache-Control': 'no-cache, private', 'Content-Type': 'application/json', 'X-Kubernetes-Pf-Flowschema-Uid': '7864e097-2ca5-48ca-b152-3a26dc8dd055', 'X-Kubernetes-Pf-Prioritylevel-Uid': '0b84b987-ffd3-4222-a927-f35069935b66', 'Date': 'Thu, 23 Jan 2025 16:38:48 GMT', 'Content-Length': '255'})
HTTP response body: {"kind":"Status","apiVersion":"v1","metadata":{},"status":"Failure","message":"object is being deleted: StatefulSet.apps \"rmqlocal\ already exists","reason":"AlreadyExists","details":{"name":"rmqlocal","group":"apps","kind":"StatefulSet"},"code":409}
```

Solution Steps:

To resolve this issue, follow these steps:

1. Navigate to the node shell in which rmqlocal-0 pod scheduled and executed following command:

   ```sh
   df -h | grep <rmqlocal-0 pod  pvc name> 
   ```

2. Change the ownership of the files using command:

   ```sh
   chown -R 1000:1000 <path from above command out put>
   ```

   **Note**: The 1000:1000 represents the user ID (UID) and group ID (GID) associated with the securityContext.
  These values can vary, so make sure to replace them with the correct UID and GID from your specific environment.

3. Restart the rmqlocal-0 pod after changing the ownership. Repeat steps 1 and 2 for all other RabbitMQ pods.
4. Run the Deployer job with upgrade mode to apply the changes.
