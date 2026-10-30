---
name: troubleshoot-rabbitmq
description: Diagnose Qubership RabbitMQ Prometheus alerts (NoMetrics, ClusterError, SomePodsAreNotWorking, MemoryAlarm, DiskAlarm), cluster formation and network partitions, queue or vhost data corruption, memory/disk alarms, .erlang.cookie and NFS storage errors, operator StatefulSet conflicts, and failed pre-upgrade Jobs. Use when triaging RabbitMQ tickets, rmqlocal pods not joining the cluster, blocked publishers, "vhost is down" errors, or operator and Deployer job failures.
---

# Troubleshooting RabbitMQ

Qubership RabbitMQ is a RabbitMQ cluster that a kopf-based operator
deploys and reconciles in Kubernetes or OpenShift. Clients connect
straight to the `rabbitmq` Service; the operator only manages the
cluster.

[references/troubleshooting.md](./references/troubleshooting.md) is the fact source for known failure
modes. It is a copy of `docs/public/troubleshooting.md` in this
repository. Do **not** read it in full for a single symptom.
[references/installation.md](./references/installation.md) is the fact source for known failure
modes. It is a copy of `docs/public/installation.md` in this
repository. Do **not** read it in full for a single symptom.

## Architecture

```text
RabbitMQ namespace
  Helm release ──► rabbitmq-operator (kopf) ──watches──► RabbitMQService CR rabbitmq-service
                         │ creates / reconciles
                         ▼
  StatefulSet rmqlocal ──► pods rmqlocal-N, PVCs default-vct-name-rmqlocal-N
  Service rabbitmq (clients :5672 / :15672) · headless Service rmqlocal (node names)
  ServiceMonitor rabbitmq-service-monitor ──► :15692 rabbitmq_prometheus
  optional: rabbitmq-backup-daemon (definitions backup, DR) · telegraf (external RabbitMQ only)
```

- The **operator**, not Helm, creates the StatefulSet and Services.
  Helm renders the CR, ConfigMap `rabbitmq-config`, and the secrets.
  Chart sources: `operator/charts/helm/rabbitmq`. Operator code:
  `operator/src/handler.py`.
- Default mode uses `rabbit_peer_discovery_k8s`. Node names are
  `rabbit@rmqlocal-N.rmqlocal.<namespace>.svc.cluster.local`, so
  clustering needs Kubernetes API access from the pod and working DNS.
- Hostpath mode (`rabbitmq.hostpath_configuration: true`) creates one
  StatefulSet `rmqlocal-N` per node. Pods are `rmqlocal-N-0`, peer
  discovery is `classic_config`, and pods are pinned to node hostnames.
- The StatefulSet update strategy is **OnDelete**. A changed parameter
  reaches running pods only with `rabbitmq.auto_reboot: true` (the
  operator restarts pods one at a time and checks the cluster) or after
  the pods are deleted.
- Cluster formation runs only on the **first** start of a node. The
  marker is `/var/lib/rabbitmq/started_at_least_once`. Until it exists,
  probes wait for a quorum of online nodes, and preStop **deletes
  `/var/lib/rabbitmq/*`** when the pod stops.
- Probes after the first start: liveness runs `check_running` and
  `check_local_alarms`; readiness adds `check_virtual_hosts`. An active
  memory/disk alarm therefore restarts the pod, and a down vhost keeps
  it NotReady.

## Reading the reference file

1. Grep headers with line numbers first:
   `grep -n '^#' references/troubleshooting.md`
2. Match the symptom against the jump table below (or the raw headers
   if the table is stale).
3. Read from the matched header through the **next header of the same
   or higher level**. A `##` section includes its `###` children; stop
   at the next `##` or `#`. Never load the whole file for one lookup.

## Symptom → reference section

| Symptom | Header in references/troubleshooting.md |
| --- | --- |
| Alert `NoMetrics`; no `rabbitmq_identity_info` series | NoMetrics |
| Alert `ClusterError`; more than one `rabbitmq_cluster` in the namespace | ClusterError |
| Alert `SomePodsAreNotWorking`; app stopped by `rabbitmqctl stop_app` | SomePodsAreNotWorking |
| Alert `MemoryAlarm` | MemoryAlarm |
| Alert `DiskAlarm` (free disk below 50 MB) | DiskAlarm |
| Before any action: is the monitoring pod up? | Dispositions |
| Persistent pods never formed one cluster on first install | Cluster Formation |
| `cluster_status` shows partitions; pause_minority / autoheal | Network Partition Recovery |
| `Failed to get nodes from k8s`, `nxdomain`, `rabbit_mnesia:init_from_config` crash | RabbitMQ Does Not Have Enough Permissions to Form a Cluster |
| Boot fails with `rabbit_queue_index,parse_segment_entries` | Queue Index Corruption |
| `rabbit_variable_queue` `function_clause`, `Restarting crashed queue` | Queue Message Corruption |
| `vhost '…' is down`, `not_a_dets_file … recovery.dets` | Vhost is Down due to a Corrupted Recovery File |
| Pod lost or redeployed; `rabbit_connection_tracking` `no_exists` errors | RabbitMQ Pod Outage |
| `rabbit_disk_monitor` terminating, `unparseable` | RabbitMQ Process Failure |
| `memory resource limit alarm set`, publishers blocked | Memory Limit Alarm |
| `disk resource limit alarm set`, publishers blocked | Disk Limit Alarm |
| One node behaves as out of disk or its vhosts stop after restart | Disk Failure on One Node |
| `.erlang.cookie contents do not match`, `must be accessible by owner only` | Problems with .erlang.cookie |
| `BOOT FAILED` with `error:{badmatch,{error,einval}}` on NFS | badmatch,{error,einval} error on NFS Storage |
| Operator log: `object is being deleted: StatefulSet.apps "rmqlocal" already exists` (409) | Operator Contains "Object is being deleted: statefulsets.apps already exists..." Error |
| Helm upgrade stopped by Job `rabbitmq-operator-rollout` | Pre-upgrade Job Failed |

### Other docs (not in the troubleshooting reference)

| Symptom | Doc |
| --- | --- |
| Deployer job fails: status check, unknown CRD fields, template errors, `Forbidden: updates to statefulset spec` | `docs/public/installation.md` headers starting with `Deployer Job` |
| Upgrade path, feature flags, intermediate 4.2 image | `docs/public/installation.md` header `Version Upgrade and Feature Flags` |
| Classic mirrored queues blocking 4.x | `docs/public/installation.md` header `Migration From CMQ to Quorum queues` |
| Default partition handling per replica count | `docs/public/installation.md` header `Partition handling` |
| Pod restart loops, liveness failures, more than 500 channels per connection | `docs/public/maintenance.md` header `Problems with Restarting RabbitMQ Pods and Liveness Probe` |
| Password or user change | `docs/public/maintenance.md` headers `Change RabbitMQ Default Password`, `Change RabbitMQ Username and Password` |
| Definitions backup and restore, manual message (Mnesia) backup | `docs/public/maintenance.md` header `Backup and Recovery` |
| DR switchover, `/healthz`, `/sitemanager` | `docs/public/disasterRecovery.md` |
| Dashboards and alert expressions | `docs/public/monitoring.md` |
| Ports, default user, TLS secrets, certificate renewal | `docs/public/security.md`, `docs/public/TLS.md` |

Start from the exact error text, the pod name (`rmqlocal-N` or
`rmqlocal-N-0`), and whether the failure is in a RabbitMQ pod, in the
operator, or in a Helm hook Job. Check attachments for logs and custom
resources before asking for them.

## Deploy channel

The chart is installed and upgraded by the **Deployer job** (or
`helm upgrade` with the same parameters file). Parameter names match
chart values.

Phrase config changes as: set deployment parameter `<key>` to
`<value>` and run the Deployer job in `upgrade` mode. Remember
OnDelete: without `rabbitmq.auto_reboot: true` the change reaches pods
only after they restart.

Do **not** recommend `kubectl edit` of StatefulSet `rmqlocal`, its
pods, or ConfigMap `rabbitmq-config` as a fix. The operator owns them
and overwrites manual changes on the next reconcile.

Failed install or upgrade — check in this order:

1. Hook Job `rabbitmq-operator-rollout` (`pre-upgrade`,
   `hook-delete-policy: before-hook-creation,hook-succeeded` — gone on
   success, left on failure). It reads running versions, rejects
   unsupported version jumps, and scales the operator to 0 for a version
   step. See `Pre-upgrade Job Failed` in the reference.
2. Operator logs: `kubectl logs deployment/rabbitmq-operator`. kopf
   `PermanentError` is **not retried**; fix the cause and rerun the
   upgrade:
   - `please create RabbitMQ secret.` — `rabbitmq-default-secret` is
     missing.
   - `RabbitMQ pods are not ready` / `RabbitMQ cluster fails to come
     up.` — pods or `/api/nodes` did not reach the replica count in
     time; go to the RabbitMQ pod logs.
   - `Changing storage configuration is not allowed.` — storage mode
     changed on upgrade; reinstall is required.
3. CR status: `kubectl get rabbitmqservices rabbitmq-service -o yaml`.

### Important deployment parameters

| Parameter | Default | Meaning |
| --- | --- | --- |
| `rabbitmq.replicas` | `3` | Cluster size; also picks the default partition handling. |
| `rabbitmq.cluster_partition_handling` | `""` | Empty → `autoheal` below 3 replicas, `pause_minority` from 3. |
| `rabbitmq.auto_reboot` | `false` | Roll pods one at a time after a config change. |
| `rabbitmq.resources` | cpu `1`, memory `2Gi` (requests = limits), storage `1024Mi` | Pod resources and PVC size. |
| `rabbitmq.custom_params.rabbitmq_vm_memory_high_watermark` | `80%` | Memory alarm threshold, share of the memory limit. |
| `rabbitmq.custom_params.rabbitmq_cluster_name` | `rabbitmq` | `rabbitmq_cluster` label that the alerts match. |
| `rabbitmq.hostpath_configuration` | `false` | Hostpath mode. Never change it on upgrade. |
| `rabbitmq.clean_rabbitmq_pvs` | `false` | **Wipes all data** (messages, queues, users, vhosts) on upgrade. |
| `rabbitmq.fsGroup` / `rabbitmq.runAsUser` | unset | Ownership of files on the PV. |
| `rabbitmq.deleteStatefulSetOnForbiddenUpdate` | `true` | Orphan-delete and recreate `rmqlocal` on immutable-field changes. |
| `rabbitmq.perQueueMetrics` | unset | Per-queue metrics; can drastically increase resource usage. |
| `MONITORING_ENABLED` / `rabbitmqPrometheusMonitoring` | unset | Enables the `rabbitmq_prometheus` plugin. Without it every alert is `NoMetrics`. |
| `disasterRecovery.mode` | `""` | `active`, `standby`, or `disabled`. |

### Secrets

| Secret | Content |
| --- | --- |
| `rabbitmq-default-secret` | `user`, `password`, `rmqcookie` (Erlang cookie). Projected into pods at `/etc/secrets/rabbitmq-pod-secrets`. |
| `rabbitmq-tls-secret` | `tls.crt`, `tls.key`, `ca.crt`, mounted at `/tls`. |
| `rabbitmq-monitoring` | Monitoring pod settings. |

A change to `user` / `password` in `rabbitmq-default-secret` makes the
operator change the password (or delete the old user), then restart
every `rmqlocal` pod one at a time. It is skipped with
`RabbitMQ pods are not ready, skip changing credentials` if any pod is
not ready. The default user is the break-glass administrator and must
not be deleted.

## Forbidden actions

- Reinstall or wipe data (`rabbitmq.clean_rabbitmq_pvs: true`, PVC
  delete, `rm` under `/var/lib/rabbitmq`) without stating that all
  messages, queues, users, and vhosts on that node are lost and getting
  confirmation. Prefer the narrow fix in the reference section first.
- Delete or restart pods of the **trusted** partition before the
  isolated nodes rejoin — follow `Network Partition Recovery` order.
- Delete the PVC of a pod with a healthy disk to "rejoin" it. A fresh
  PVC is only for `Disk Failure on One Node`.
- Delete `.erlang.cookie` while RabbitMQ runs under the wrong user: it
  is recreated at once with the same wrong permissions. Stop RabbitMQ
  on that node first.
- Change `rabbitmq.hostpath_configuration` or the storage class during
  an upgrade. Moving between storage modes needs a reinstall.
- Disable `statusProvisioner.enabled` for a Deployer job run; the job
  then fails.
- Upgrade a broken cluster. Make it healthy (or reinstall the same
  version) first, then upgrade.
- Skip a minor version or the intermediate image on the 3.13 → 4.x
  path, or upgrade to 4.x while `classic_queue_mirroring` is in use.
- Recommend live `kubectl edit` of operator-owned objects as a
  permanent fix — change the deployment parameter and run the upgrade.

## Clustering and partitions

- `rabbitmq-diagnostics cluster_status` from any reachable pod shows
  running nodes and partitions. `rabbitmq-diagnostics check_cluster`
  confirms recovery.
- `pause_minority` (3+ replicas) stops RabbitMQ on the minority side;
  those pods go NotReady while the majority keeps serving. `autoheal`
  (1–2 replicas) restarts the losing side and can drop in-flight
  messages.
- `ClusterError` with a healthy cluster usually means a second
  RabbitMQ in the same namespace: count distinct `rabbitmq_cluster`
  values before touching pods.
- Non-mirrored classic queue messages on a pod **without** a PVC are
  lost when that pod is lost. Event logging queues are quorum queues.

## DR

`standby` is not a crash. In standby only the backup daemon is scaled
down; RabbitMQ pods keep running, and DR replicates **definitions**
only (vhosts, users, queues, exchanges), never messages.

- Check the role: `GET http://rabbitmq-disaster-recovery.<NS>:8080/sitemanager`
  (`mode`, `status`) or CR `status.disasterRecoveryStatus`.
- Health: `GET /healthz` returns `up`, `degraded`, `down`, or
  `disable`.
- Failed switchover: retry in the order active → standby, then
  standby → active (`docs/public/disasterRecovery.md` header
  `Troubleshooting`).

Do not recommend restoring definitions or rebuilding the cluster
solely because the site is in standby.

## First checks

1. Monitoring is alive (`Dispositions`): if `NoMetrics` fires too, fix
   metrics first — other alerts are blind.
2. `kubectl get pods -l app=rmqlocal` and
   `rabbitmq-diagnostics cluster_status` — pod count, readiness, and
   partitions.
3. RabbitMQ pod logs for the exact error line, then operator logs
   (`deployment/rabbitmq-operator`) for reconcile errors.
4. Free disk and memory against the alarm thresholds, and whether the
   PV is NFS or hostpath.
5. Then jump to the matching reference section.
