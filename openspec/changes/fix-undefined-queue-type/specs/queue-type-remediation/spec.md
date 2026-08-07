## Purpose

Ensures every RabbitMQ vhost and queue in a cluster has an explicit, non-`undefined` queue type, preventing backup/restore failures caused by the string `"undefined"` propagating into exported definitions.

## ADDED Requirements

### Requirement: Broker-level default queue type

The broker configuration SHALL include `default_queue_type = classic` so that all new vhosts and queues receive a concrete type without requiring per-resource declaration.

#### Scenario: New vhost inherits classic default

- **WHEN** a new vhost is created without specifying `default_queue_type`
- **THEN** the broker assigns `classic` as the default queue type for that vhost

---

### Requirement: Scheduled vhost remediation

The operator SHALL run a remediation job on a daily schedule (at 00:00 UTC) that iterates all vhosts and sets `default_queue_type = classic` on any vhost where the value is `undefined` (as the atom or as the string `"undefined"`).

#### Scenario: Vhost with unset default queue type is remediated

- **WHEN** the daily remediation runs
- **AND** a vhost has `default_queue_type` not set (atom `undefined`)
- **THEN** the operator sets `default_queue_type` to `classic` on that vhost

#### Scenario: Vhost with string-undefined default queue type is remediated

- **WHEN** the daily remediation runs
- **AND** a vhost has `default_queue_type` equal to the string `"undefined"`
- **THEN** the operator sets `default_queue_type` to `classic` on that vhost

#### Scenario: Vhost with explicit queue type is not changed

- **WHEN** the daily remediation runs
- **AND** a vhost already has an explicit `default_queue_type` (e.g. `classic`, `quorum`, `stream`)
- **THEN** the operator leaves that vhost unchanged and logs the existing value

---

### Requirement: Scheduled queue remediation

The operator SHALL run a remediation job on the same daily schedule that iterates all queues and sets `x-queue-type = classic` on any queue where the argument is absent or equal to the string `"undefined"`.

#### Scenario: Queue with unset x-queue-type is remediated

- **WHEN** the daily remediation runs
- **AND** a queue has no `x-queue-type` argument
- **THEN** the operator sets `x-queue-type` to `classic` on that queue

#### Scenario: Queue with string-undefined x-queue-type is remediated

- **WHEN** the daily remediation runs
- **AND** a queue has `x-queue-type` equal to the string `"undefined"`
- **THEN** the operator sets `x-queue-type` to `classic` on that queue

#### Scenario: Queue with explicit x-queue-type is not changed

- **WHEN** the daily remediation runs
- **AND** a queue already has an explicit `x-queue-type` (e.g. `classic`, `quorum`, `stream`)
- **THEN** the operator leaves that queue unchanged and logs the existing value

---

### Requirement: Remediation on operator startup

The operator SHALL also execute the vhost and queue remediation at startup (initial delay = 0) so that clusters self-heal after an operator restart or upgrade without waiting for the next nightly window.

#### Scenario: Operator restart triggers remediation

- **WHEN** the operator pod starts
- **THEN** the vhost and queue remediation runs once before the daily schedule begins

---

### Requirement: Opt-out via Helm value

The remediation timer and the `default_queue_type` config line SHALL be controllable via a Helm value so that operators running clusters where quorum or stream queues are the intentional default can disable the feature without patching the image.

#### Scenario: Feature disabled via Helm value

- **WHEN** the Helm value `rabbitmq.setDefaultQueueTypeClassic` is set to `false`
- **THEN** `default_queue_type` is NOT added to `rabbitmq.conf`
- **AND** the remediation timer is NOT registered in the operator

#### Scenario: Feature enabled by default

- **WHEN** the Helm value `rabbitmq.setDefaultQueueTypeClassic` is not explicitly set
- **THEN** it defaults to `true` and both the config line and the timer are active
