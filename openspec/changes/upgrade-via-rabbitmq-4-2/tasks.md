# Tasks

## 1. Version file and manifest images

- [ ] 1.1 Add `rabbitmq-docker/rabbitmq.properties` with `rabbitmq.3.version=3.13`, `rabbitmq.4.version=4.2`, and `intermediateVersions=4.2`. Add `rabbitmq.rabbitmqVersion` and `rabbitmq.intermediateVersions` to `values.yaml`, matching that file, plus a map from each intermediate version to its image. Declare those shapes on `$defs.rabbitmq` in `values.schema.json`, which sets `additionalProperties: false`. Verify a check fails if the values differ from the properties file, `helm template` succeeds, and `helm template` fails when an unknown property is added under `rabbitmq`.
- [ ] 1.2 Render the target `rabbitmqVersion` and each intermediate image, keyed by its `major.minor`, into `templates/cr.yaml` on `spec.rabbitmq`. Add those properties to the storage `v2` schema in `operator/charts/helm/rabbitmq/crds/crd.yaml`, and to `docs/sources/crds` if that copy includes `spec.rabbitmq`. Verify the rendered custom resource shows target `4.2` and an intermediate image entry `4.2` distinct from `dockerImage`.
- [ ] 1.3 Document the properties file, `rabbitmq.rabbitmqVersion`, and `rabbitmq.intermediateVersions` in `docs/public/installation.md`: versions are `major.minor` from the file, the image name is that version, and deleting an intermediate entry removes that stop. Verify those three facts appear.

## 2. Chain function

- [ ] 2.1 Add a pure function that, given the oldest running version, the target version, and `intermediateVersions`, returns the ordered version steps or a rejection. Compare `major.minor` only. Skip an entry equal to the initial version or the target. Cover `4.0.1` and `4.1.2` with list `4.2` and target `4.2` as one target-line step; initial `4.2` with target `5.1` and list `4.2,4.7,5.0` starting at `4.7`; `4.0` → `5.1` through the intermediate images `4.2`, `4.7`, and `5.0` then the target; `4.7` skipping `4.2`; `5.0` → `5.1` as a single target step; `4.2.1` and `4.2.9` as the same version; a fresh install; a missing image for a selected step; an empty target; a line value whose major is not 4. Verify with `python -m unittest` from `operator/`.
- [ ] 2.2 Add a unit case that removes `4.7` from `4.2,4.7,5.0` and shows `4.2` is followed by `5.0`. Verify that test passes without any version constant in the operator.

## 3. Operator applies the chain

- [ ] 3.1 Copy `rabbitmq.properties` into the operator image and parse it before enabling feature flags or calling `update_config`. Read `rabbitmqctl version` on every RabbitMQ pod and keep `major.minor`. If a pod's exec output cannot be parsed, try management `/api/overview` field `rabbitmq_version` for that pod. If any pod is still unreadable, a line major does not match its key, or the target version is empty, set status `FAILED` and raise `kopf.PermanentError` before feature flags and before `update_config`. Verify the unreadable-version test and the line-major test still pass.
- [ ] 3.2 Let StatefulSet generation take an image override looked up from the custom resource by `major.minor`. Run the chain function first. On rejection, do not enable feature flags and do not call `update_config`; the status names the running version, the target version, and the missing image or version. On acceptance, for each step enable feature flags, write that step's image, delete pods because the strategy is `OnDelete`, and wait until every node reports that step's major and minor before the next step. Do not write an intermediate image into `spec.rabbitmq.dockerImage`. A version step restarts pods even when `auto_reboot` is false. On resume, continue a chain whose pods are not yet on the current step's image, and return without a restart when every node reports the target major.minor and the pods already use the target image. Verify the missing-image test and the mid-chain "one node still old" case do not apply the next image.
- [ ] 3.3 Update the Version Upgrade section of `docs/public/installation.md` so a multi-step upgrade follows `intermediateVersions`, a stop equal to the initial version or the target is skipped, patch is ignored, and a missing image for a selected step fails before the cluster changes. Verify those four outcomes are stated.

## 4. Images a shipped intermediate names

- [ ] 4.1 Add `rabbitmq-docker/intermediate-versions/4.2/Dockerfile` for the shipped intermediate, pinned to RabbitMQ 4.2 and independent of `rabbitmq-docker/4.0/Dockerfile`. Pass `rabbitmq.4.version` and `rabbitmq.3.version` into the line Dockerfiles as build arguments, without setting them as runtime environment variables, and fail the build when the upstream tag's major.minor differs. Register `qubership-rabbitmq-image-4.2` in `.qubership/docker-build-config.cfg` and `.github/charts-values-update-config.yaml`. Keep `.github/workflows/push.yml` in sync if it still lists RabbitMQ images. Verify a listed version without a directory under `rabbitmq-docker/intermediate-versions/` fails the same check.

## Workflow follow-up

- Archive the change after review with `/opsx-archive`.
