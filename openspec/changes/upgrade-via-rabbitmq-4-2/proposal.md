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
- Each entry of `intermediateVersions` has its own Dockerfile at `rabbitmq-docker/intermediate-versions/<major.minor>`. This change adds `rabbitmq-docker/intermediate-versions/4.2`. That image is separate from the line image declared by `rabbitmq.4.version`. The promoted reference lives in the chart manifest under that version. The operator does not parse an image tag or digest.
- The build passes each line version into its Dockerfile as a build argument. The same file is copied into the operator image. On an upgrade the operator reads `major.minor` from every RabbitMQ pod and the target line from the version file. An intermediate step is skipped when that version equals the initial major.minor or the target. The next step is otherwise the first remaining entry strictly between them. If none remains, the only step is the target line image. With the file above, target `4.2` skips the `4.2` intermediate, so `4.0` and `4.1` go straight to the line image. A fresh install uses the target image and does not walk the list.
- The operator applies the computed steps itself, in order. For each step it enables stable feature flags on the version that is still running, writes the manifest image for that `major.minor` to the StatefulSet, and waits until every node reports that major and minor before the next step.
- If a pod version cannot be read, a line version has the wrong major, the target version is absent, or the manifest has no image for a selected version, the operator rejects the upgrade before it enables feature flags and before it changes a StatefulSet. The error names the running version, the target version, and the reason.
- The existing 3.x to 4.x mirrored-queue gate stays. `3.13` is the 3-line image. It is not inserted into a 4.x chain unless `intermediateVersions` lists it.

## Capabilities

### New Capabilities

- `rabbitmq-upgrade-path`: how the operator builds and executes a RabbitMQ upgrade from the version file and the manifest images named by those versions.

### Modified Capabilities

- None. `openspec/specs/` has no existing capabilities.

## Impact

- Operator reconcile in `operator/src/handler.py`: read the version file, read pod versions as `major.minor`, resolve each step's image from the custom resource, apply the computed steps.
- Version file consumed by the broker image build and copied into the operator image.
- Helm chart: `values.yaml`, `values.schema.json`, `templates/cr.yaml`, and the `v2` schema of the `RabbitMQService` CRD. The manifest must carry an image for every version the file names, and `additionalProperties` is false.
- `rabbitmq-docker/intermediate-versions/4.2` is registered in `.qubership/docker-build-config.cfg` and `.github/charts-values-update-config.yaml`. Each later entry of `intermediateVersions` gets the same kind of directory and registration.
- Upgrade documentation in `docs/public/installation.md`.
- Automated tests for a direct upgrade, a multi-step list, a skipped prefix, a patch that does not change the step, and a rejected upgrade.
