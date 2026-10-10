# Proposal

## Why

RabbitMQ does not allow every jump between minor versions. The delivery ships one target image, and the operator applies that image in one step, so a cluster on an older minor must find intermediate builds by hand or risk an unsupported upgrade. CPCAP-16000 requires the delivery and the operator to own that path. The set of required stops will change as new RabbitMQ versions are published, so the path cannot be a single hardcoded hop.

## What Changes

- Add one version file as the source of RabbitMQ versions. It stores each shipped line as `major.minor` and an ordered list named `intermediateVersions`. It does not store image references. The file shipped with this change is:

```properties
rabbitmq.3.version=3.13
rabbitmq.4.version=4.2
intermediateVersions=4.2
```

- A line key accepts only that major. `rabbitmq.4.version=5.1` is invalid. A later major is a new key, for example `rabbitmq.5.version=5.1`. Further stops are added by editing `intermediateVersions`, for example `4.2,4.7,5.0`, not by changing operator code.
- Each entry of `intermediateVersions` has its own Dockerfile at `rabbitmq-docker/intermediate-versions/<major.minor>`. This change adds `rabbitmq-docker/intermediate-versions/4.2`. That image is separate from the line image declared by `rabbitmq.4.version`. The chart lists the promoted reference in `intermediateImages`. The operator reads `major.minor` from the repository name and ignores the tag and digest.
- The version file is copied into the operator image. On an upgrade the operator reads `major.minor` from every RabbitMQ pod and the target line from the version file. An intermediate step is skipped when that version equals the initial major.minor or the target. The next step is otherwise the first remaining entry strictly between them. If none remains, the only step is the target line image. With the file above, target `4.2` skips the `4.2` intermediate, so `4.0` and `4.1` go straight to the line image. A fresh install uses the target image and does not walk the list.
- The operator applies the computed steps itself, in order. For each step it enables stable feature flags on the version that is still running, writes the manifest image for that `major.minor` to the StatefulSet, and waits until every node reports that major and minor before the next step.
- If a pod version cannot be read, a line version has the wrong major, the target version is absent, or the manifest has no image for a selected version, the operator rejects the upgrade before it enables feature flags and before it changes a StatefulSet. The error names the running version, the target version, and the reason.
- The existing 3.x to 4.x mirrored-queue gate stays. `3.13` is the 3-line image. It is not inserted into a 4.x chain unless `intermediateVersions` lists it.
- A pre-upgrade hook reads the new `rabbitmq.properties` from the chart operator image and `rabbitmqctl version` from the RabbitMQ pods. When that plan contains an intermediate step, the hook writes the chart operator image into the `rabbitmq-operator` Deployment and waits until a pod with that image is Ready. Helm changes the custom resource only after that. The hook does not restart the previous operator pod in place. When the plan has no intermediate step, the hook leaves the Deployment unchanged and the operator image moves with the rest of the chart.

## Capabilities

### New Capabilities

- `rabbitmq-upgrade-path`: how the operator builds and executes a RabbitMQ upgrade from the version file and the intermediate image whose repository name ends with that version.

### Modified Capabilities

- None. `openspec/specs/` has no existing capabilities.

## Impact

- Operator reconcile in `operator/src/handler.py`: read the version file, read pod versions as `major.minor`, resolve each step's image from the custom resource, apply the computed steps.
- Version file copied into the operator image. Broker Dockerfiles keep their upstream image written in the file.
- Helm chart: `values.yaml`, `values.schema.json`, `templates/cr.yaml`, and the `v2` schema of the `RabbitMQService` CRD. Chart values hold `intermediateImages`, not the version numbers. The manifest must list an image whose repository name ends with each intermediate version, and `additionalProperties` is false.
- `rabbitmq-docker/intermediate-versions/4.2` is registered in `.qubership/docker-build-config.cfg` and `.github/charts-values-update-config.yaml`. Each later entry of `intermediateVersions` gets the same kind of directory and registration.
- Pre-upgrade hook under `templates/pre-deploy/`: it updates the operator Deployment to the chart image before the custom resource only when the new plan has an intermediate step.
- Upgrade documentation in `docs/public/installation.md`.
- Automated tests for a direct upgrade, a multi-step list, a skipped prefix, a patch that does not change the step, and a rejected upgrade.
