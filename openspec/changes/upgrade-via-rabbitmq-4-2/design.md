# Design

## Context

See proposal.md for why this change exists. The behavior contract is `specs/rabbitmq-upgrade-path/spec.md`.

Today Helm writes one `spec.rabbitmq.dockerImage`, and `on_update` applies it in one StatefulSet replacement. Image tags in this repo are release names or branches plus a digest. `get_target_rabbitmq_version` therefore cannot see the RabbitMQ minor that the Dockerfile actually installs. The StatefulSet update strategy is `OnDelete`, so a new image string does not restart pods until the operator deletes them. `podManagementPolicy: Parallel` only affects scale order.

## Goals / Non-Goals

**Goals:**

- Compute upgrade steps from an ordered list of `major.minor` values.
- Let a release add or remove a stop by editing that list.
- Resolve an intermediate step to the image built from `rabbitmq-docker/intermediate-versions/<major.minor>`.
- Skip that image when the running major.minor or the target equals the entry.

**Non-Goals:**

- Parsing a RabbitMQ version out of an image tag or digest.
- Storing image references in the version file.
- Comparing patch numbers. `4.2.1` and `4.2.9` are the same step.
- Detecting a downgrade by inspecting image bytes.
- Replacing the Helm 3.x mirrored-queue gate.
- Renaming the `rabbitmq-docker/4.0` directory.

## Decisions

### 1. One version file, images in the manifest

**Chosen:** `operator/rabbitmq.properties` is the only hand-written source of versions. It sits in the operator image build context and is copied into the image. The file shipped with this change is `rabbitmq.3.version=3.13`, `rabbitmq.4.version=4.2`, and `intermediateVersions=4.2`. A line value's major must equal the key. `5.1` is declared as `rabbitmq.5.version`, never as the value of `rabbitmq.4.version`. The file is copied into the operator image, and the operator parses that copy for the target line and the intermediate list.

Each intermediate version has its own Dockerfile at `rabbitmq-docker/intermediate-versions/<major.minor>`. This change adds `rabbitmq-docker/intermediate-versions/4.2`. That build is not the line image: the line image stays `rabbitmq-docker/4.0/Dockerfile` and `dockerImage`. The intermediate image reference is a list entry whose repository name ends with that `major.minor`. The operator reads the version from that name and ignores the tag and digest. The image is used only for an intermediate step. The operator does not read a registry reference from the properties file.

The upstream image and its digest stay written in each broker Dockerfile. The properties file is not read by those builds.

**Alternative considered:** `from` / `until` rules with an image field on each rule. Rejected. The stop list is a single ordered array, and the image name is the version, so a second image field repeats the same value.

### 2. The next stop is the next greater intermediate

**Chosen:** compare `major.minor` only. Skip an `intermediateVersions` entry equal to the initial major.minor or equal to the target. The next step is the first remaining entry strictly between them, and that step uses the intermediate image. If none remains, the only step is the target line image.

With the shipped file the list is `4.2` and the target is `4.2`, so the intermediate step is skipped. `4.0` and `4.1` both go to the line image in one step. The `4.2` intermediate image is still built, for a later target that is above `4.2`. Example: target `rabbitmq.5.version=5.1` and `intermediateVersions=4.2,4.7,5.0` walks `4.0` through the intermediate images `4.2`, `4.7`, and `5.0`, then the target line image. Initial `4.2` skips the `4.2` image and starts at `4.7`. Initial `4.7` skips `4.2` and `4.7` and starts at `5.0`. `3.13` is not inserted unless the list contains it.

**Alternative considered:** treat every `rabbitmq.<major>.version` below the target as an implicit stop. Rejected. A line key is the image built for that major. A stop is added only by listing it.

### 3. Missing data fails before any mutation

**Chosen:** build the whole chain first. If any pod version is unreadable, a line version has the wrong major, the target version is empty, or a selected version has no image on the custom resource, `update_status(FAILED, ...)` and raise `kopf.PermanentError` before feature flags and before `update_config`. The error includes the oldest running version, the target version, and the missing piece.

### 4. Each accepted step uses the existing roll

**Chosen:** `generate_stateful_set_body` takes an image override. The operator does not write an intermediate image back into `spec.rabbitmq.dockerImage`. For each step, after the chain is accepted:

1. Enable stable feature flags on the version still running.
2. Write that step's manifest image to the StatefulSet and delete the pods. `OnDelete` does not restart them by itself.
3. Wait until every node reports that step's major and minor. On the storage-class path, wait between pods. On hostpath, the existing code deletes every pod and then checks once.
4. Only then take the next step.

A failed flag enablement stops the chain. The cluster stays on the version that is already up. A version-changing step restarts pods even when `auto_reboot` is false. A reconcile that does not change the RabbitMQ image still honors `auto_reboot`.

`on.resume` continues a chain when the operator process restarts and pods are not yet on the target. It returns without a restart when every node already reports the target major.minor and the pods already use the target image. If the running version cannot be read yet, it retries without setting `FAILED`. When no StatefulSet exists it installs through `on_create`.

Once an intermediate version has started and enabled its flags, rolling the data directory back below that version is not supported.

### 6. Roll the operator only when an intermediate step remains

**Chosen:** the pre-upgrade hook runs the chart operator image, which carries `rabbitmq.properties`. It reads `rabbitmqctl version` from the RabbitMQ pods and builds the same plan as the operator. It patches the operator Deployment to that image and waits until the pod is Ready only when the plan contains an intermediate step. A direct step to the target image, or no step at all, leaves the running operator in place. Helm applies the custom resource after the hook. The next release that adds a stop between the running version and the new target rolls the operator again, because the decision is the plan in the new image, not a marker left on the pod.

**Alternative considered:** roll whenever a pod annotation is absent. Rejected. The annotation stays after the first upgrade, so a later target above the current one would still be applied by the previous binary and its old properties file.

### 5. Tests cover the chain function

**Chosen:** unit-test the pure chain function for the shipped file (`4.0.1` and `4.1.2` with list `4.2` and target `4.2` skip the intermediate and use the line image), initial `4.2` with target `5.1` and list `4.2,4.7,5.0` starting at `4.7`, the `4.0` → `5.1` walk through those intermediate images, a source of `4.7` skipping `4.2`, a direct last hop, equal major.minor of `4.2.1` and `4.2.9`, a fresh install, a missing image for a selected step, an unreadable version, a line major mismatch, and a removed intermediate. Robot image tests compare steady-state images and do not drive a multi-step upgrade.

Intermediate images are not added to `rabbitmq.monitoredImages`. After a successful upgrade no steady-state workload runs them.

## Risks / Trade-offs

- [A second copy of the versions is written into chart values] → `values.yaml` does not carry `rabbitmqVersion` or `intermediateVersions`. The operator reads both from the properties file. Chart values hold only the promoted image references.
- [The line image and the intermediate image share a version] → an intermediate step uses only `intermediate-versions/<version>`. A step skipped because it equals the target uses `dockerImage`.
- [Crash between steps] → the next `on_resume` or `on_update` reads the oldest node and skips completed landings. A version that is not readable yet retries and does not mark the custom resource `FAILED`.
- [The previous-release operator handles the custom resource first] → the pre-upgrade hook rolls that Deployment only when the new properties file puts an intermediate step between the running version and the target. A direct upgrade does not roll it.
- [Hostpath deletes every pod before the cluster check] → accepted. That path keeps its current restart behavior for every step.
- [3.x to 4.x is not in the intermediate list] → the Helm mirrored-queue gate remains the control for that jump.

## Migration Plan

1. Ship the version file with `3.13`, `4.2`, and `intermediateVersions=4.2`, plus `rabbitmq-docker/intermediate-versions/4.2`. The current target skips applying that image.
2. A later release that needs another stop appends that `major.minor` to `intermediateVersions` and adds `rabbitmq-docker/intermediate-versions/<major.minor>` before customers receive the chart.
3. Removing an entry from the list removes that stop from later upgrades. It does not roll a cluster back.

## Open Questions

- None.
