## Why

RabbitMQ serializes queue and vhost metadata via the Management API definitions endpoint. When `default_queue_type` is not explicitly set on a vhost, or `x-queue-type` is absent on a queue, RabbitMQ stores the value as the string `"undefined"` rather than a concrete type. During backup/restore this propagates into the exported JSON and causes restore failures or silent misconfigurations (see Broadcom KB #423308). Setting `classic` as the explicit default eliminates this class of corruption.

## What Changes

- Add `default_queue_type = classic` to `rabbitmq.conf` via the Helm chart so all new vhosts inherit a concrete default at broker level.
- Add a Kopf daily timer handler in the operator (`handler.py`) that runs at 00:00 and executes two `rabbitmqctl eval` commands on the primary RabbitMQ pod:
  1. Iterate all vhosts — set `default_queue_type = classic` on any vhost where the value is `undefined` or not set.
  2. Iterate all queues — set `x-queue-type = classic` on any queue where the argument is `undefined` or not set.
- The same remediation runs automatically on operator restart (initial delay = 0) so upgrades self-heal without waiting for the nightly window.

## Capabilities

### New Capabilities

- `queue-type-remediation`: Operator-driven scheduled and startup remediation that ensures every vhost and queue has an explicit, non-`undefined` queue type.

### Modified Capabilities

- *(none — no existing spec-level behavior changes)*

## Impact

- **`operator/src/handler.py`**: new `@kopf.timer` handler; reuses existing `exec_command_in_pod` / `KubernetesHelper` machinery.
- **`operator/charts/helm/rabbitmq/templates/_helpers.tpl`** or **`rabbitmq-configmap.yaml`**: injects `default_queue_type = classic` into `rabbitmq.conf`.
- **`operator/charts/helm/rabbitmq/values.yaml`**: new boolean toggle `rabbitmq.setDefaultQueueTypeClassic` (default `true`) to allow opt-out if a cluster intentionally uses quorum or stream as default.
- No API changes, no schema changes, no backup-daemon changes.
- Idempotent: vhosts/queues already carrying an explicit type are logged and skipped.
