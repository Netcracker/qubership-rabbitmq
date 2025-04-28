[[_TOC_]]

# RabbitMQ Service

## Repository structure

* `./docs` - directory with actual documentation for the component.
* `./grafana` - directory with Grafana Dashboard for RabbitMQ.
* `./openshift` - directory with scripts for deploying to Openshift environment.
* `./operator` - directory with operator code & HELM chart for RabbitMQ.
* `./operator/operator-robot-image` - directory with **actual** Robot Framework tests for RabbitMQ.
* `./performance-tests-image` - directory with sources for RabbitMQ performance test component.
* `./rabbitmq-backup-daemon` - directory with sources for RabbitMQ Backup Daemon component.
* `./telegraf` - directory with sources for monitoring component for RabbitMQ.
* `./zabbix` - directory with sources for Zabbix component.

## How to start

### Deploy to k8s

#### Pure helm

1. Build operator and integration tests, if you need non-main versions.
2. Prepare kubeconfig on you host machine to work with target cluster.
3. Prepare `sample.yaml` file with deployment parameters, which should contains custom docker images if it is needed.
4. Store `sample.yaml` file in `/operator/charts/helm/rabbitmq` directory.
5. Go to `/operator/charts/helm/rabbitmq` directory.
6. Run the following command:

  ```sh
  helm install rabbitmq ./ -f sample.yaml -n <TARGET_NAMESPACE>
  ```

### Smoke tests

There is no smoke tests.

### How to debug

Not applicable

### How to troubleshoot

There are no well-defined rules for troubleshooting, as each task is unique, but there are some tips that can do:

* Deploy parameters.
* Application manifest.
* Logs from all RabbitMQ service pods.

Also, developer can take a look on [Troubleshooting guide](/docs/public/troubleshooting.md).
## Evergreen strategy

To keep the component up to date, the following activities should be performed regularly:

* Vulnerabilities fixing.
* RabbitMQ upgrade.
* Bug-fixing, improvement and feature implementation in operator, monitoring or other RabbitMQ components.

## Useful links

* [Installation guide](/docs/public/installation.md).
* [Troubleshooting guide](/docs/public/troubleshooting.md).
* [Internal Developer Guide](/docs/internal/developing.md).
