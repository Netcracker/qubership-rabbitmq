---
name: troubleshoot-rabbitmq
description: RabbitMQ — operational guidance, common failure modes, and Helm value paths for `rabbitmq.conf`-equivalent settings via the THIRDPARTY.Platform.Services / RabbitMQ operator. Load when the ticket touches a RabbitMQ cluster, vhost / queue / exchange behaviour, memory / disk-alarm watermarks, HiPE compilation, mirrored / quorum queues, or an `RABBITMQ_*` runtime env knob.
---

# Troubleshoot RabbitMQ

Use this skill when investigating issues related to:

- **rabbitmq-operator** — kopf reconcile, CR `RabbitMQService`,
  `PermanentError`.
- **Cluster formation and partitions** — peer discovery,
  `pause_minority` / `autoheal`.
- **Resource alarms** — memory/disk alarm, `OOMKilled`, blocked
  publishers.
- **Storage** — PVC full, NFS `einval`, hostpath mode, disk failure on
  one node.
- **Data integrity** — queue index/message corruption, vhost recovery
  file.
- **Pod lifecycle** — readiness/liveness, OnDelete, `auto_reboot`.
- **Security** — `rabbitmq-default-secret`, password change,
  `.erlang.cookie`, TLS.
- **Monitoring** — `NoMetrics`, `ClusterError`, `SomePodsAreNotWorking`.
- **Backup daemon and DR** — definitions backup, switchover, standby.
- **Upgrades** — `rabbitmq-operator-rollout`, 3.13 → 4.x, feature
  flags, CMQ → quorum.
- **Log analysis** — `grep` of attached RabbitMQ pod, operator, and
  pre-upgrade Job logs against the documented error signatures
  (`Log Analysis Tips`).

This skill applies to any Qubership RabbitMQ cluster managed by the
kopf-based `rabbitmq-operator` deployed from
`operator/charts/helm/rabbitmq`. The operator owns reconciliation;
manual changes to operator-owned objects are overwritten on the next
reconcile.

The reference files are copies of `docs/public/*.md` in this
repository, synced by the `Sync Troubleshooting Skill` workflow. Do
**not** read any of them in full for a single symptom.

| Reference | Fact source for |
| --- | --- |
| [references/troubleshooting.md](./references/troubleshooting.md) | Alerts and known failure modes (primary). |
| [references/maintenance.md](./references/maintenance.md) | Password/user change, backup and restore, ports, pod restarts and liveness. |

Other guides are not bundled with the skill. When the repository is
available, read them by path with the same header-first method; when
it is not, rely on the facts already summarised in this file:

| Repository path | Fact source for |
| --- | --- |
| `docs/public/installation.md` | Deployment parameters, Deployer job errors, upgrade path, partition handling. |
| `docs/public/disasterRecovery.md` | DR modes, switchover, `/healthz`, `/sitemanager`. |
| `docs/public/monitoring.md` | Dashboards, metrics, and alert expressions. |
| `docs/public/security.md` | Ports, default user, secrets, security settings. |
| `docs/public/TLS.md` | TLS secrets and certificate renewal. |

## Component Overview

### Operator architecture

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

Key components:

- `rabbitmq-operator` (kopf) — Deployment that reconciles CR
  `rabbitmq-service`. With DR enabled it also serves `/healthz` and
  `/sitemanager` behind Service `rabbitmq-disaster-recovery`.
- StatefulSet `rmqlocal` (in hostpath mode one StatefulSet
  `rmqlocal-N` per node), Service `rabbitmq` for clients, and headless
  Service `rmqlocal` for node names.
- `rabbitmq-backup-daemon` — definitions backup and restore, DR
  replication.
- Monitoring — the `rabbitmq_prometheus` plugin scraped by
  ServiceMonitor `rabbitmq-service-monitor`. Telegraf is used only for
  an external RabbitMQ.
- Helm hook Jobs — `rabbitmq-operator-rollout` (`pre-upgrade`) and
  Status Provisioner `rabbitmq-status-provisioner`
  (`post-install,post-upgrade`).

Behaviour that drives most failures:

- The **operator**, not Helm, creates the StatefulSet and Services.
  Helm renders the CR, ConfigMap `rabbitmq-config`, and the secrets.
  Operator code: `operator/src/handler.py`.
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

### Critical configuration paths

Chart: `operator/charts/helm/rabbitmq` — defaults in `values.yaml`,
manifests in `templates/`, CRD in `crds/crd.yaml`.

#### Important deployment parameters

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
| `rabbitmq.customConfigProperties` | `[deprecated_features.permit.transient_nonexcl_queues = true]` | Extra `rabbitmq.conf` lines. Replacing the list drops the default line. |
| `rabbitmq.queueMigration.enabled` | `false` | Enables the CMQ → quorum queue migration plugin (3.13, Mnesia only). |
| `MONITORING_ENABLED` / `rabbitmqPrometheusMonitoring` | unset | Enables the `rabbitmq_prometheus` plugin. Without it every alert is `NoMetrics`. |
| `disasterRecovery.mode` | `""` | `active`, `standby`, or `disabled`. |

`rabbitmq.clean_rabbitmq_pvs`, `rabbitmq.fsGroup`,
`rabbitmq.runAsUser`, `rabbitmq.perQueueMetrics`,
`MONITORING_ENABLED`, `rabbitmqPrometheusMonitoring`, and
`disasterRecovery.mode` have no entry in `values.yaml`; the defaults
above come from `templates/cr.yaml`, `templates/_helpers.tpl`, and
`templates/rabbitmq_per_object_service_monitor.yaml`.

#### Secrets

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

#### Helm value paths for engine settings

There is no `CUSTOM_PARAMS` deployer variable and no `RABBITMQ_*`
environment knob for broker tuning in this chart. Helm renders
`rabbitmq.conf` and `advanced.config` into ConfigMap `rabbitmq-config`
(`operator/charts/helm/rabbitmq/templates/rabbitmq-configmap.yaml`)
from these values:

| Setting | Value path | Rendered as |
| --- | --- | --- |
| Memory alarm threshold | `rabbitmq.custom_params.rabbitmq_vm_memory_high_watermark` (`80%`) | `vm_memory_high_watermark.relative = 0.80` |
| Memory the broker sees | `rabbitmq.resources.limits.memory` (`2Gi`) | `total_memory_available_override_value = 2000MiB` |
| Cluster name / alert label | `rabbitmq.custom_params.rabbitmq_cluster_name` | `cluster_name` |
| Partition handling | `rabbitmq.cluster_partition_handling` | `cluster_partition_handling` |
| Default queue type | `rabbitmq.setDefaultQueueTypeClassic` (`true`) | `default_queue_type = classic` + daily vhost remediation |
| Plugins | `rabbitmq.enabledPlugins` (list) | `enabled_plugins` |
| Any other `rabbitmq.conf` key | `rabbitmq.customConfigProperties` (list of `key = value` lines) | appended verbatim |
| `advanced.config` terms | `rabbitmq.customAdvancedProperties` (list of Erlang terms) | joined into `advanced.config` |
| Container env | `rabbitmq.environmentVariables` (list of `NAME=value`) | pod env |

Template traps (verified with `helm template`):

- The watermark helper keeps the **first two characters** and prefixes
  `0.`. Only a two-digit `NN%` from `10%` to `99%` is valid: `5%` renders
  `0.5%` (boot fails), `100%` renders `0.10`, `0.4` renders `0.0.`, and
  absolute values such as `1GB` are not supported.
- The memory helper mishandles fractional `G`/`Gi`: `1.5Gi` renders
  `500MiB`. Use whole `Gi` or `Mi` (`3072Mi`). Whole `Gi` is rendered as
  `N000MiB`, slightly below the real limit.
- `environmentVariables` entries are split on `=`; an entry with more
  than one `=` is dropped with only an operator log error.
- The image entrypoint exits with code 1 when any deprecated variable
  is set: `RABBITMQ_VM_MEMORY_HIGH_WATERMARK`, `RABBITMQ_DEFAULT_USER_FILE`,
  `RABBITMQ_DEFAULT_PASS_FILE`, `RABBITMQ_SSL_*`,
  `RABBITMQ_MANAGEMENT_SSL_*` (`rabbitmq-docker/docker-entrypoint.sh`).
- An unknown or misspelled `customConfigProperties` key makes the node
  fail to boot. Changes reach pods only after restart (OnDelete).

#### Queue types and plugins
- With `rabbitmq.setDefaultQueueTypeClassic: true`, the operator sets
  `classic` daily on vhosts whose default queue type is missing or
  `undefined`. Set it to `false` only when the cluster intentionally
  defaults to quorum or stream queues.
- Shovel is always enabled. Federation and other plugins need
  `rabbitmq.enabledPlugins`. Upstreams, shovels, and policies are
  runtime definitions owned by the application team — the operator does
  not create or revert them.

### Forbidden actions

Never recommend these without explicit user approval and ticket
evidence:

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
- Set `RABBITMQ_VM_MEMORY_HIGH_WATERMARK`, `RABBITMQ_SSL_*`,
  `RABBITMQ_MANAGEMENT_SSL_*`, `RABBITMQ_DEFAULT_USER_FILE`, or
  `RABBITMQ_DEFAULT_PASS_FILE` through `rabbitmq.environmentVariables`.
  The entrypoint exits and every pod goes into CrashLoopBackOff.
- Give the watermark in any format other than two-digit `NN%`, or the
  memory limit as fractional `G`/`Gi`.
- Repeat in `customConfigProperties` a key that the chart already
  renders from a dedicated parameter (`vm_memory_high_watermark.*`,
  `total_memory_available_override_value`, `cluster_name`,
  `cluster_partition_handling`, `default_queue_type`,
  `cluster_formation.*`, TLS `ssl_options.*` / `listeners.*`). Change
  the dedicated parameter instead.
- Edit `rabbitmq.conf`, `advanced.config`, or `enabled_plugins` inside
  a pod. The files come from ConfigMap `rabbitmq-config` and are lost on
  restart.
- Run `rabbitmqctl stop_app` outside a documented procedure, or
  without `/tmp/BACKUP_FLAG_FILE` in the pod: liveness (`check_running`)
  restarts the pod, and a stopped app raises `SomePodsAreNotWorking`.
- Recommend `rabbitmqctl forget_cluster_node`, `reset`, `force_reset`,
  or `force_boot`. No reference procedure uses them; use
  `Network Partition Recovery`, `Cluster Formation`, or
  `Disk Failure on One Node`.
- Recommend classic mirroring (`ha-mode` policies) as an HA fix.
  Use quorum queues.
- Create or change policies, users, or vhosts on a DR `standby` site
  as a fix: the switchover to `active` restores the last backup from
  the other site and overwrites them.
- Recommend HiPE (`RABBITMQ_HIPE_COMPILE`, `hipe_compile`). The images
  run RabbitMQ 3.13 and 4.x, which have no HiPE support.

## Common Failure Modes

Use these after the matching reference section confirms the failure is
a sizing, configuration, or cluster-formation problem, not data
corruption.

### Memory alarm / OOMKilled

Symptom: `memory resource limit alarm set`, `MemoryAlarm`,
`connection.blocked` on clients, liveness restarts while the alarm is
active, or `OOMKilled` (exit code 137).

- Check `rabbitmq-diagnostics memory_breakdown` and
  `rabbitmq-diagnostics alarms` first. Large `connection_*` or
  `queue_procs` usage points to client behaviour (more than 500
  channels per connection, unconsumed backlog), not to the limit.
- Tune `rabbitmq.resources` (requests = limits, whole `Gi` or `Mi`)
  and `rabbitmq.custom_params.rabbitmq_vm_memory_high_watermark`. The
  watermark is a share of `total_memory_available_override_value`,
  which comes from `rabbitmq.resources.limits.memory`.
- Raising the watermark without raising the memory limit leads to
  `OOMKilled`. Keep it at or below `80%`; above it the broker can
  exceed the container limit and dashboards show wrong memory data
  ([maintenance.md](./references/maintenance.md)
  `Problems with Restarting RabbitMQ Pods and Liveness Probe`).

### Disk alarm / PVC full

Symptom: `disk resource limit alarm set`, `DiskAlarm`, publishers
blocked, `No space left on device`, or a pod that does not start after
a restart with a full PV.

- Free space (drain or purge queues) or grow the storage by the
  documented procedure. The chart does not resize existing PVCs
  `default-vct-name-rmqlocal-N`: `rabbitmq.resources.storage` only
  changes the volume claim template
  (`docs/public/installation.md` header starting
  with `Deployer Job Fails and Operator Contains "Forbidden`). Growing
  an existing PVC depends on `allowVolumeExpansion` of its storage
  class; keep `rabbitmq.resources.storage` equal to the new size.
- Do not lower the alarm threshold and do not delete PVCs.
  `rabbitmq.clean_rabbitmq_pvs` is forbidden without confirmation.
- The chart sets no `disk_free_limit`; RabbitMQ uses its 50 MB default,
  and the `DiskAlarm` Prometheus rule hard-codes the same 50 MB.
  `disk_free_limit.relative` is a multiple of broker memory, not a
  share of the disk: with the default 2Gi limit and 1024Mi PVC, `0.5`
  or higher puts the node in alarm almost at once.

### Network partition

Symptom: `rabbitmq-diagnostics cluster_status` lists partitions, nodes
run standalone, or pods on the minority side are NotReady.

- The default behaviour comes from `rabbitmq.cluster_partition_handling`.
  Empty means `autoheal` below 3 replicas and `pause_minority` from 3.
  Keep the default unless the ticket shows the mode itself is wrong.
- Recover with `Network Partition Recovery`; do not invent a
  `rabbitmqctl` sequence.

### Cluster does not form / pods NotReady on first start

Symptom: persistent pods never formed one cluster on first install, or
new pods stay NotReady waiting for a quorum.

- Check RBAC and DNS: `Failed to get nodes from k8s`, `nxdomain`, or a
  `rabbit_mnesia:init_from_config` crash point to
  `RabbitMQ Does Not Have Enough Permissions to Form a Cluster`.
- Check whether `/var/lib/rabbitmq/started_at_least_once` exists.
  Formation runs only before it is written.
- Until the first successful start, preStop deletes
  `/var/lib/rabbitmq/*`, so restarting such a pod discards its data.
  Then follow `Cluster Formation`.

## Reading the reference files

1. Grep headers with line numbers first, for example:
   `grep -n '^#' references/troubleshooting.md`
2. Match the symptom against the jump tables below (or the raw headers
   if the tables are stale).
3. Read from the matched header through the **next header of the same
   or higher level**. A `##` section includes its `###` children; stop
   at the next `##` or `#`. Never load the whole file for one lookup.

## Symptom → reference section

Tickets rarely name the Prometheus alert. Match on what the reporter
actually sees — pod status, `kubectl describe` events, log lines,
client errors — not only on alert names.

| Symptom | Header in [references/troubleshooting.md](./references/troubleshooting.md) |
| --- | --- |
| Alert `NoMetrics`; no `rabbitmq_identity_info` series; empty RabbitMQ dashboards | NoMetrics |
| Alert `ClusterError`; more than one `rabbitmq_cluster` in the namespace | ClusterError |
| Alert `SomePodsAreNotWorking`; app stopped by `rabbitmqctl stop_app`; pod Running but node absent from `cluster_status` | SomePodsAreNotWorking |
| Alert `MemoryAlarm`; memory near `vm_memory_high_watermark`; `rabbitmq-diagnostics alarms` lists a memory alarm | MemoryAlarm, then Memory Limit Alarm |
| Pod `OOMKilled` (`Last State: Terminated, Reason: OOMKilled`, exit code 137); restarts under load | MemoryAlarm, then [maintenance.md](./references/maintenance.md) `Problems with Restarting RabbitMQ Pods and Liveness Probe` |
| Pod in `CrashLoopBackOff` or restarting on liveness failure with a memory or disk alarm active | MemoryAlarm / DiskAlarm, then Memory Limit Alarm / Disk Limit Alarm |
| Alert `DiskAlarm` (free disk below 50 MB); PV almost full; `No space left on device` | DiskAlarm, then Disk Limit Alarm |
| Clients report `connection.blocked`, publishers hang or time out, consumers still work | Memory Limit Alarm / Disk Limit Alarm |
| Pod stuck NotReady after restart while `check_virtual_hosts` fails | Vhost is Down due to a Corrupted Recovery File |
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

### Other reference files

| Symptom | Reference and header |
| --- | --- |
| Deployer job fails: status check, unknown CRD fields, template errors, `Forbidden: updates to statefulset spec` | `docs/public/installation.md` headers starting with `Deployer Job` |
| Upgrade path, feature flags, intermediate 4.2 image | `docs/public/installation.md` header `Version Upgrade and Feature Flags` |
| Classic mirrored queues blocking 4.x | `docs/public/installation.md` header `Migration From CMQ to Quorum queues` |
| Default partition handling per replica count | `docs/public/installation.md` header `Partition handling` |
| Pod restart loops, liveness failures, more than 500 channels per connection | [maintenance.md](./references/maintenance.md) header `Problems with Restarting RabbitMQ Pods and Liveness Probe` |
| Password or user change | [maintenance.md](./references/maintenance.md) headers `Change RabbitMQ Default Password`, `Change RabbitMQ Username and Password` |
| Definitions backup and restore, manual message (Mnesia) backup | [maintenance.md](./references/maintenance.md) header `Backup and Recovery` |
| DR switchover, `/healthz`, `/sitemanager` | `docs/public/disasterRecovery.md` |
| Dashboards and alert expressions | `docs/public/monitoring.md` |
| Ports, default user, TLS secrets, certificate renewal | `docs/public/security.md`, `docs/public/TLS.md` |

Start from the exact error text, the pod name (`rmqlocal-N` or
`rmqlocal-N-0`), and whether the failure is in a RabbitMQ pod, in the
operator, or in a Helm hook Job. Check attachments for logs and custom
resources before asking for them.

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
  standby → active (`docs/public/disasterRecovery.md`
  header `Troubleshooting`).

Do not recommend restoring definitions or rebuilding the cluster
solely because the site is in standby.

## Deploy channel

The chart is installed and upgraded by the **Deployer job** (or
`helm upgrade` with the same parameters file). Parameter names match
chart values. Phrase changes as described in `Recommendation
discipline` below.

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
4. CRD or Helm release problems: unknown fields after an upgrade →
   `docs/public/installation.md` `CRD Upgrade` and
   `Automatic CRD Upgrade`; Kubernetes upgraded before the application
   → `What to Do if a Kubernetes Version is Upgraded Before Application?`.

## Log Analysis Tips

### First checks

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

### Searching provided logs

Logs attached to a ticket are the primary evidence. Search them with
`grep` before you read them: do not load a whole log, and do not ask
for logs that are already attached.

1. **Classify each file by source.** The source decides which
   signatures apply:

   ```sh
   grep -lF 'kopf.objects' <files>        # operator (deployment/rabbitmq-operator)
   grep -lF 'rabbit@rmqlocal' <files>     # RabbitMQ pods (rmqlocal-N, rmqlocal-N-0)
   grep -lE '^running .*, target ' <files> # pre-upgrade Job rabbitmq-operator-rollout
   ```

   Use `zgrep` with the same options for `.gz` files. Unpack an
   archive into its own new, empty directory before you search it.

2. **Run the signature sweep** over all files. It uses fixed strings
   (`-F`), because the signatures contain `{ } ( ) [ ] .`, and keeps
   their exact case. Do not add `-i` to `-F`: some GNU grep builds
   (for example, grep 3.0 in Git for Windows) abort on that combination.

   ```sh
   grep -nHF \
     -e 'resource limit alarm set' -e 'Publishers will be blocked' \
     -e 'vm_memory_high_watermark' -e 'No space left on device' \
     -e 'Failed to get nodes from k8s' -e 'nxdomain' -e 'init_from_config' \
     -e 'timeout_waiting_for_tables' \
     -e 'parse_segment_entries' -e 'could_not_start,rabbit' \
     -e 'rabbit_variable_queue' -e 'Restarting crashed queue' -e 'failed to initialise' \
     -e 'not_a_dets_file' -e 'recovery.dets' -e 'access to vhost' \
     -e 'rabbit_connection_tracking' -e 'tracked_connection_on_node' \
     -e 'rabbit_disk_monitor' -e 'unparseable' \
     -e '.erlang.cookie' -e 'BOOT FAILED' -e 'badmatch,{error,einval}' \
     -e 'object is being deleted' -e 'Forbidden: updates to statefulset spec' \
     -e 'PermanentError' -e 'failed with an exception' \
     -e 'please create RabbitMQ secret' -e 'RabbitMQ pods are not ready' \
     -e 'RabbitMQ cluster fails to come up' -e 'Changing storage configuration is not allowed' \
     -e 'RabbitMQ upgrade failed' -e 'Failed to enable RabbitMQ feature flags' \
     -e 'Environment variable "' -e 'Switchover failed' \
     -e 'requires RabbitMQ 3.13 or newer' -e 'classic mirrored queues are still in use' \
     -e 'downgrade is not supported' -e 'missing image' -e 'target version is absent' \
     -e 'version file is unreadable' -e 'running version could not be determined' \
     -e 'deprecated-features/used' \
     -e 'restoring operator replicas' -e 'failed to restore operator' \
     -e 'OOMKilled' -e 'Liveness probe failed' -e 'Readiness probe failed' \
     <files> | cut -c1-300 | head -200
   ```

   For a large log, count first and look at the distinct hits:
   `grep -ohF -e '<sig1>' -e '<sig2>' <file> | sort | uniq -c | sort -rn`.

3. **Map every hit** with the signature table below to a reference
   header, then read that section as described in `Reading the
   reference files`.

4. **Read the multi-line context.** Erlang crash reports and kopf
   tracebacks span many lines, and the cause is inside the block, not in
   the first line:

   ```sh
   grep -nF -A12 'Reason for termination' <file>   # Erlang generic server crash
   grep -nF -A20 'BOOT FAILED' <file>              # boot error description
   grep -nF -A40 'failed with an exception' <file> | grep -E 'ApiException|Reason:|"message"|PermanentError'
   ```

5. **Find the first failure.** Take the earliest matching line for each
   node. Later `CRASH REPORT`, `Restarting crashed queue`, and kopf
   `Will retry.` lines are usually consequences. Note the node
   (`rabbit@rmqlocal-N…`), vhost, queue, and file path from the line.

6. **If no signature matches,** search generically, then map the
   process or module name to a header:

   ```sh
   grep -nE -i '\[(error|critical)\]|ERROR|CRASH REPORT|terminating|partition' <file> | head -100
   ```

   Say in the assessment that no documented signature matched.

7. **Quote the evidence.** In the assessment, give the file name, line
   number, and the exact line for every signature you used.

For a live cluster, read the same sources directly. For a pod in
CrashLoopBackOff or after a liveness restart, read the **previous**
container:

```sh
kubectl logs -n <ns> <rmqlocal-pod> --previous
kubectl describe pod -n <ns> <rmqlocal-pod>     # OOMKilled, exit code 137, probe failures
kubectl logs -n <ns> deployment/rabbitmq-operator
kubectl logs -n <ns> job/rabbitmq-operator-rollout
kubectl get rabbitmqservices rabbitmq-service -n <ns> -o yaml
```

### Error signatures

Unmarked strings are quoted in the guides. Strings marked † are
exact messages from the operator code (`operator/src`) that the guides
do not quote: the message names its cause, and the header column gives
the closest section.

RabbitMQ pods (`rmqlocal-N`, `rmqlocal-N-0`):

| Fixed string in the log | Header (`troubleshooting.md` unless named) |
| --- | --- |
| `memory resource limit alarm set` | Memory Limit Alarm, MemoryAlarm |
| `vm_memory_high_watermark clear` | Memory Limit Alarm (the alarm has cleared) |
| `disk resource limit alarm set` | Disk Limit Alarm, DiskAlarm |
| `Publishers will be blocked until this alarm clears` | The alarm line just above it: Memory Limit Alarm or Disk Limit Alarm |
| `No space left on device` | DiskAlarm, Disk Limit Alarm |
| `Failed to get nodes from k8s`, `nxdomain`, `rabbit_mnesia:init_from_config` | RabbitMQ Does Not Have Enough Permissions to Form a Cluster |
| `timeout_waiting_for_tables` | Network Partition Recovery (step 6) |
| `rabbit_queue_index,parse_segment_entries` (inside `could_not_start,rabbit`) | Queue Index Corruption |
| `rabbit_variable_queue`, `Restarting crashed queue`, `failed to initialise` | Queue Message Corruption |
| `not_a_dets_file` with `recovery.dets` | Vhost is Down due to a Corrupted Recovery File |
| Client side: `access to vhost '…' refused` / `vhost '…' is down` | Vhost is Down due to a Corrupted Recovery File |
| `Generic server rabbit_connection_tracking terminating`, `no_exists`, `tracked_connection_on_node` | RabbitMQ Pod Outage |
| `Generic server rabbit_disk_monitor terminating`, `unparseable` | RabbitMQ Process Failure |
| `.erlang.cookie contents do not match`, `changing permissions of '/var/lib/rabbitmq/.erlang.cookie'`, `must be accessible by owner only` | Problems with .erlang.cookie |
| `BOOT FAILED` with `error:{badmatch,{error,einval}}` | badmatch,{error,einval} error on NFS Storage |
| `BOOT FAILED` with another error | Read the `Error description:` block and map its module; an unknown `rabbitmq.conf` key also fails the boot (see `Template traps`) |
| Events: `OOMKilled`, exit code 137 | MemoryAlarm, then [maintenance.md](./references/maintenance.md) `Problems with Restarting RabbitMQ Pods and Liveness Probe` |
| Events: `Liveness probe failed` / `Readiness probe failed` | Liveness runs `check_running` and `check_local_alarms`, so search the pod log for an alarm. Readiness also runs `check_virtual_hosts`, so search for a down vhost. |

Operator (`deployment/rabbitmq-operator`, kopf):

| Fixed string in the log | Header or meaning |
| --- | --- |
| `object is being deleted: StatefulSet.apps "rmqlocal" already exists` (409) | Operator Contains "Object is being deleted: statefulsets.apps already exists..." Error |
| `Forbidden: updates to statefulset spec for fields` (422) | `docs/public/installation.md` `Deployer Job Fails and Operator Contains "Forbidden: updates to statefulset spec for fields..." Error` |
| `Handler 'on_create'` / `Handler 'on_update'` … `failed with an exception. Will retry.` | Retried. Read the traceback's `ApiException` and `"message"` lines. |
| † `PermanentError` | Not retried. Use the message on the same line (below), fix the cause, and rerun the upgrade. |
| † `please create RabbitMQ secret.` | `rabbitmq-default-secret` is missing (`Deploy channel`) |
| † `RabbitMQ pods are not ready` / `RabbitMQ cluster fails to come up.` | Pods did not reach the replica count; continue with the RabbitMQ pod logs |
| † `RabbitMQ pods are not ready, skip changing credentials` | The password change was skipped; see `Secrets` and [maintenance.md](./references/maintenance.md) `Change RabbitMQ Default Password` |
| † `Changing storage configuration is not allowed.` | Storage mode changed on upgrade; reinstall is required |
| † `Failed to enable RabbitMQ feature flags in pod` | `docs/public/installation.md` `Version Upgrade and Feature Flags` |
| † `RabbitMQ upgrade failed.` (CR status `failed to enable all feature flags`) | `docs/public/installation.md` `Version Upgrade and Feature Flags` |
| `timeout_waiting_for_tables` | Network Partition Recovery (step 6) |
| † `Environment variable "…" is incorrect` | An `rabbitmq.environmentVariables` entry does not contain exactly one `=` and was dropped |
| † `Switchover failed` | `docs/public/disasterRecovery.md` `Troubleshooting` |

Pre-upgrade Job (`job/rabbitmq-operator-rollout`). Its decision and
error lines start with `running <version>, target <version>`. Start
from `Pre-upgrade Job Failed` for all of them:

| Fixed string in the log | Next header |
| --- | --- |
| † `upgrade to 4.x requires RabbitMQ 3.13 or newer` | `docs/public/installation.md` `Version Upgrade and Feature Flags` |
| † `classic mirrored queues are still in use` | `docs/public/installation.md` `Migration From CMQ to Quorum queues` |
| † `missing image <major.minor>` | The intermediate or target image is not in the CR; check `rabbitmq.intermediateImages` and `Version Upgrade and Feature Flags` |
| † `downgrade is not supported` | The target is older than the running version |
| † `target version is absent`, `version file is unreadable`, `running version could not be determined` | The target or running version could not be read |
| † `deprecated-features/used returned` / `failed` | The management API is unreachable from the Job |
| † `restoring operator replicas`, `failed to restore operator` | The hook failed after scaling the operator to 0; check `deployment/rabbitmq-operator` replicas |

Read-only diagnostics, run with
`kubectl exec -n <ns> <rmqlocal-pod> -- rabbitmq-diagnostics <command>`:
`cluster_status`, `alarms`, `check_running`, `check_local_alarms`,
`check_virtual_hosts`, `check_cluster`.

### Upgrade

```sh
kubectl logs -n <ns> job/rabbitmq-operator-rollout
kubectl describe job rabbitmq-operator-rollout -n <ns>
```

The Job is deleted on success; if it is absent, the pre-upgrade step
passed.

### Backup and DR

- Logs of `deployment/rabbitmq-backup-daemon`; its state is
  `GET /health` on port 8080 ([maintenance.md](./references/maintenance.md)
  header `Backup Daemon Health`).
- DR endpoints on Service `rabbitmq-disaster-recovery` (served by
  `rabbitmq-operator`): `GET /healthz` and `GET /sitemanager` on both
  sites.

## Safety

Commands in the references are recommendations for an authorized
operator, not permission to run them. Before deleting pods, PVCs, data
under `/var/lib/rabbitmq`, secrets, or certificates, changing
credentials, or setting `clean_rabbitmq_pvs`, get explicit user
approval and confirm the namespace, active/standby side, affected
data, and recovery path.

## Assessment

Report the matched reference header, the evidence that selected it,
the impact, and only the resolution steps that section supports. State
what the evidence could not answer. Do not invent a root cause.

### Recommendation discipline

- Phrase every change as: "Set deployment parameter `<key>`: `<value>`
  in the rabbitmq chart values and run the upgrade through the normal
  delivery channel (Deployer job or `helm upgrade`)."
- OnDelete: without `rabbitmq.auto_reboot: true` the change reaches
  pods only after they restart — restart the `rmqlocal` pods one at a
  time ([maintenance.md](./references/maintenance.md)
  `Change the Number of Running Pods or Configuration`).
- Do not recommend `kubectl edit` of operator-owned objects (StatefulSet
  `rmqlocal`, its pods, ConfigMap `rabbitmq-config`) as a permanent
  fix. The operator owns the StatefulSet and pods; Helm renders the
  ConfigMap. Both overwrite manual changes on the next reconcile or
  upgrade.
- Do not recommend wiping data or deleting PVCs as a fix for a
  configuration problem.
- Recommend only parameters listed in `Critical configuration paths`,
  or ones confirmed with `grep -n '<parameter>'` in
  `docs/public/installation.md` or
  `operator/charts/helm/rabbitmq/values.yaml` when the repository is
  available. Use a dedicated parameter when one exists.
- Use `customConfigProperties` only for a `rabbitmq.conf` key that is
  valid for the running RabbitMQ version (3.13 or 4.x). When you cannot
  confirm the key, omit the recommendation — do not fall back to
  `rabbitmqctl set_parameter`, env variables, or in-pod file edits.
- When a list parameter is changed, give the full resulting list.
  Helm replaces lists, so defaults such as
  `deprecated_features.permit.transient_nonexcl_queues = true` must be
  kept.
- Name the data impact and restart impact of every recommendation.

## When to Escalate

Escalate when:

- the queue index, message store, or a vhost is corrupted and there is
  no definitions or messages backup;
- the cluster does not form while DNS and RBAC work;
- a kopf `PermanentError` repeats after its stated cause is fixed;
- a partition does not recover with `Network Partition Recovery`;
- a DR switchover still fails after a retry in the order
  active → standby, standby → active;
- the 3.13 → 4.x upgrade or feature flags fail after the documented
  steps;
- the operator crashes or loops on reconcile.

Attach:

- logs of the operator and of the affected `rmqlocal` pods;
- `kubectl get rabbitmqservices -n <ns> -o yaml` and
  `kubectl get pods,pvc -n <ns> -o wide`;
- output of `rabbitmq-diagnostics cluster_status` and
  `rabbitmq-diagnostics alarms`;
- logs of Job `rabbitmq-operator-rollout` (for upgrades);
- `/healthz` and `/sitemanager` from both sites (for DR).
