# Spec Delta

## Purpose

Defines how a RabbitMQ upgrade chooses intermediate versions from an ordered major.minor list and applies the manifest image for each step before the target image.

## ADDED Requirements

### Requirement: Versions are major and minor only

The delivery SHALL declare each RabbitMQ line version and each intermediate version as major.minor only. A line version's major SHALL equal the line it belongs to. The operator SHALL compare only major and minor and SHALL ignore the patch. The operator SHALL NOT infer a version from an image tag or digest.

#### Scenario: Patch does not change the step

- **WHEN** the oldest running version is 4.0.1
- **AND** the target version is 4.2
- **AND** the intermediate list contains 4.2
- **THEN** the 4.2 intermediate step is skipped because it equals the target
- **AND** the only step is the target image
- **AND** a running version of 4.1.2 produces the same single step

#### Scenario: A line version keeps its major

- **WHEN** the version declared for line 4 has a major other than 4
- **THEN** the operator rejects the upgrade before it enables feature flags or updates a StatefulSet

### Requirement: The next step is the next intermediate version

The operator SHALL skip an intermediate version equal to the initial major.minor or equal to the target. The next step SHALL be the first remaining intermediate strictly between them. When none remains, the only step SHALL be the target image. An intermediate step SHALL use that version's own intermediate image, not the target line image.

#### Scenario: Declared stops are visited in order

- **WHEN** the oldest running major.minor is 4.0
- **AND** the target version is 5.1
- **AND** the intermediate list is 4.2, then 4.7, then 5.0
- **THEN** the chain is 4.2, then 4.7, then 5.0, then the target image

#### Scenario: Initial version skips that intermediate

- **WHEN** the oldest running major.minor is 4.2
- **AND** the target version is 5.1
- **AND** the intermediate list is 4.2, then 4.7, then 5.0
- **THEN** the chain does not apply the 4.2 intermediate image
- **AND** the chain starts at 4.7 and then 5.0 and then the target image

#### Scenario: A later source skips earlier stops

- **WHEN** the oldest running major.minor is 4.7
- **AND** the target version is 5.1
- **AND** the intermediate list is 4.2, then 4.7, then 5.0
- **THEN** the chain does not include 4.2
- **AND** the chain starts at 5.0 and then the target image

#### Scenario: No intermediate remains before the target

- **WHEN** the oldest running major.minor is 5.0
- **AND** the target version is 5.1
- **AND** no intermediate is strictly between them
- **THEN** the only step is the target image

#### Scenario: Fresh install does not walk the list

- **WHEN** no RabbitMQ cluster is present
- **THEN** the operator creates the cluster from the target image

### Requirement: Running version is read from every node

On an existing cluster, the operator SHALL read the RabbitMQ version reported by every running node before it changes the cluster, and SHALL plan the upgrade from the oldest major.minor.

#### Scenario: Nodes disagree

- **WHEN** one node reports 4.2.9 and another node reports 4.0.1
- **THEN** the operator plans the upgrade from 4.0

#### Scenario: A node version cannot be read

- **WHEN** an upgrade is requested for an existing cluster
- **AND** the operator cannot read the version of any node
- **THEN** the operator rejects the upgrade before it enables feature flags or updates a StatefulSet
- **AND** the error states that the running version could not be determined

### Requirement: The image for a step is the manifest entry of that version

The operator SHALL resolve the image for a step from the custom resource entry named by that step's major.minor. It SHALL NOT take an image reference from the version file. A missing target version or a missing image for a selected version SHALL reject the upgrade before feature flags and before a StatefulSet update.

#### Scenario: A required image was removed

- **WHEN** the chain selects version 4.2
- **AND** the custom resource has no image named 4.2
- **THEN** the operator does not enable feature flags and does not change the cluster
- **AND** the error names the running version, the target version, and the missing image

#### Scenario: The 3-line image is not an implicit stop

- **WHEN** the running major.minor is 4.0
- **AND** line 3.13 is declared
- **AND** the intermediate list does not contain 3.13
- **THEN** the chain does not include 3.13

### Requirement: The operator applies the chain in order

The operator SHALL apply each step of an accepted chain before the next step. Before it changes the image, it SHALL enable the stable feature flags of the version that is still running. It SHALL NOT start the next step until every node reports the major and minor of the step just applied.

#### Scenario: Flags run only after the chain is accepted

- **WHEN** the chain is rejected
- **THEN** the operator does not enable feature flags

#### Scenario: The next step waits for every node

- **WHEN** a step has been applied
- **AND** one node does not yet report that step's major and minor
- **THEN** the operator does not apply the following step

#### Scenario: Feature flags fail between steps

- **WHEN** a migration step is running
- **AND** enabling feature flags on that version fails
- **THEN** the operator does not apply the following step
- **AND** the error names the failed feature-flag step

### Requirement: Only manifest images for selected versions are used

During an upgrade the operator SHALL write only the custom resource image named by the current step's major.minor. It SHALL leave the target image reference on the custom resource unchanged while an intermediate step is in progress.

#### Scenario: An intermediate image is not stored as the target

- **WHEN** the operator applies an intermediate version
- **THEN** the target image reference on the custom resource stays the final image
