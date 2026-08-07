## Context

See proposal.md — Why for the motivation.

The operator runs as a Kopf-based Python process. It already has two `@kopf.timer` handlers (`shovel_monitoring` at line 1663, `cluster_monitoring` at line 1680 in `handler.py`) that follow the pattern: decorate a function with `@kopf.timer`, pass `interval` in seconds and `initial_delay`. Execution against RabbitMQ pods goes through `KubernetesHelper.exec_command_in_pod()` (line 313), which streams commands to the pod via the Kubernetes API — the same channel used today for `rabbitmqctl change_password`, `enable_feature_flag`, and plugin management.

`rabbitmq.conf` is generated from `templates/rabbitmq-configmap.yaml`, which delegates to the `rabbitmq.clusterConfiguration` helper in `_helpers.tpl`. User-supplied lines can be added today via `values.yaml:rabbitmq.customConfigProperties[]`. The new line fits cleanly into either the helper template directly (guarded by a Helm `if`) or via a new dedicated Helm block.

## Goals / Non-Goals

**Goals:**
- Set `default_queue_type = classic` in `rabbitmq.conf` at deploy time.
- Run a nightly Kopf timer (00:00) that fixes existing vhosts and queues whose queue type is `undefined` or unset.
- Run the same fix at operator startup so upgrades self-heal immediately.
- Provide a single Helm opt-out toggle (`rabbitmq.setDefaultQueueTypeClassic`, default `true`).

**Non-Goals:**
- Changing queue types away from `quorum` or `stream` — only `undefined`/unset values are touched.
- Modifying the backup daemon or any code outside the operator and Helm chart.
- Adding a REST/CR API to trigger the remediation on demand.

## Decisions

### 1. Kopf timer vs. Kopf daemon

**Chosen:** `@kopf.timer` with `interval=86400` (24 h) and `initial_delay=0`.

`@kopf.timer` fires on a fixed wall-clock interval starting from operator startup, which is the exact behaviour needed: run once immediately (startup self-heal), then every 24 hours. `@kopf.daemon` is a long-running background coroutine — appropriate for continuous watch loops, not for a periodic batch job.

**Alternative considered:** a Kubernetes CronJob in the Helm chart that runs `kubectl exec`. Rejected — requires extra RBAC, a separate Pod/SA, and duplicates infrastructure already inside the operator. The operator already holds exec privileges and the Kubernetes client.

### 2. Executing rabbitmqctl eval vs. Management API

**Chosen:** `rabbitmqctl eval` via `exec_command_in_pod`.

The two eval scripts (provided by the user) directly manipulate the Mnesia/Khepri metadata layer (`rabbit_db_vhost:merge_metadata`, `rabbit_db_queue:update`). This is necessary because the Management API `PUT /api/vhosts/{vhost}` cannot patch only the `default_queue_type` of an existing vhost — it would require a full redeclaration. For queues, the definitions import (`POST /api/definitions`) recreates queues and risks message loss in non-classic queues.

**Alternative considered:** Management API patching. Rejected because: (a) vhost PATCH is not supported for metadata-only changes; (b) queue redeclaration via definitions can be destructive.

### 3. Helm guard placement

**Chosen:** A dedicated `{{- if .Values.rabbitmq.setDefaultQueueTypeClassic }}` block inside `rabbitmq.clusterConfiguration` in `_helpers.tpl`, emitting `default_queue_type = classic`.

The `customConfigProperties` mechanism exists but is user-facing; adding a framework-level concern there would require users to explicitly pass it and could be accidentally removed. A dedicated guarded line in the helper template is invisible to users and controlled only by the toggle.

For the operator Python side, the timer registration is wrapped in a check of an environment variable (`RABBITMQ_SET_DEFAULT_QUEUE_TYPE_CLASSIC`, defaulting to `"true"`) that the Helm chart injects via the operator Deployment's env block. This mirrors how other feature flags are handled in the chart.

### 4. Target pod selection

**Chosen:** Run the eval on the first `Running` pod of the RabbitMQ StatefulSet (same heuristic already used for `enable_feature_flag` in handler.py).

`rabbitmqctl eval` runs on the local Erlang node, and the two scripts use global Mnesia/Khepri calls (`rabbit_vhost:list_names()`, `rabbit_amqqueue:list()`) that enumerate the full cluster state regardless of which node is queried. Any Running pod is therefore sufficient.

### 5. Timeout and error handling

The existing `exec_command_in_pod` has a 30-second timeout. For large clusters with thousands of queues this may be tight. The two eval scripts will be split into separate `exec_command_in_pod` calls (one for vhosts, one for queues), each with the default 30-second timeout. If the call raises an exception, the timer handler will log the error and return normally — Kopf will retry on the next scheduled interval. A failed run is non-fatal.

## Risks / Trade-offs

| Risk | Mitigation |
|------|-----------|
| Timeout on clusters with thousands of queues | Each eval is a single Erlang loop over in-memory data; expected sub-second even at 10k queues. If needed the timeout can be raised to 120 s without broader changes. |
| Eval writes to Mnesia/Khepri directly, bypassing validation | The only write is setting a well-known attribute to a valid value (`<<"classic">>`). The same path is used by RabbitMQ internally when a queue type is declared. |
| Operator restart mid-eval | Kopf timers are not transactional. A partial run will complete on the next trigger. Both scripts are idempotent — already-set values are skipped. |
| Feature flag disabled but config line still present after toggle change | The ConfigMap is regenerated on Helm upgrade. The operator watches the ConfigMap (`kopf.on.update` on `rabbitmq-config`) and restarts pods. No manual action needed. |

## Migration Plan

1. Helm upgrade with default values → `rabbitmq.conf` gains `default_queue_type = classic`; operator Deployment gains the env var.
2. Operator pod restarts → `@kopf.timer` fires at `initial_delay=0` → vhosts and queues with `undefined` type are patched in place.
3. Existing backups that contain `"undefined"` values are not retroactively fixed; the next backup after the operator runs will contain clean definitions.
4. **Rollback:** set `rabbitmq.setDefaultQueueTypeClassic=false` and `helm upgrade`. The config line is removed on the next pod restart; the timer is not registered. Already-patched vhosts/queues retain `classic` — this is safe and correct.
