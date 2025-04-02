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

#### Application deployer

1. Build a manifest using [Manifest building guide](#manifest).
2. Prepare Cloud Deploy Configuration:
   1. Go to the [APP-Deployer infrastructure configuration](https://cloud-deployer.qubership.org/job/INFRA/job/groovy.deploy.v3/).
   2. INFRA --> Clouds -->  find your cloud --> Namespaces --> find your namespace.
   3. If the namespace is **not presented** then:
      1. Click `Create` button and specify: namespace and credentials. 
      2. Click `Save`.
      3. Go to your namespace configuration and specify the parameters for service installing.
   4. If the namespace is presented then: just check the parameters or change them.
3. To deploy service using APP-Deployer:
   1. Go to the [APP-Deployer groovy deploy page](https://cloud-deployer.qubership.org/job/INFRA/job/groovy.deploy.v3/).
   2. Go to the `Build with Parameters` tab.
   3. Specify:
      1. Project: it is your cloud and namespace.
      2. The list is based on the information from the [APP-Deployer infrastructure configuration](https://cloud-deployer.qubership.org/job/INFRA/job/groovy.deploy.v3/). 
      3. Deploy mode - `Rolling Update`. 
      4. Artifact descriptor version --> the **application manifest**.

#### ArgoCD

The information about ArgoCD deployment can be found in [Platform ArgoCD guide](https://bass.qubership.org/display/PLAT/ArgoCD+guide).

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

#### APP-Deployer job typical errors

##### Application does not exist in the CMDB

The error like "ERROR: Application does not exist in the CMDB" means that the APP-Deployer doesn't have
configuration related to the "service-name" from application manifest.

**Solution**: check that the correct manifest is used.

##### CUSTOM_RESOURCE timeout

The error like "CUSTOM_RESOURCE timeout" means the service was deployed to the namespace, but the Custom Resource doesn't have SUCCESS status.
Usually, it is related to the service state - it might be unhealthy or repeatedly crushing.

**Solution**: there is no ready answer, need to go to namespace & check service state, operator logs to find a root cause and fix it.

## CI/CD

The main CI/CD pipeline is design to automize all basic developer routine start from code quality and finish with
deploying to stand k8s cluster.

1. `linter` - stage with jobs that run different linter to check code & documentation.
2. `build` - stage with jobs that build docker images for RabbitMQ components using DP-Builder.
3. `manifest` - stage with jobs that build manifest for current branch or release manifest using DP-Builder.
4. `cloudDeploy` - optional stage with job which deploys the manifest to `ci-master`, `miniha`, `k8s1/2` clusters using APP-Deployer.
5. `cloudDeployTests` - stage with job which deploys manifest with integration tests using APP-Deployer.
6. `manifestValidation` - optional stage with jobs that validate manifest (check is it ready to be released) and check
   vulnerabilities.

## Evergreen strategy

To keep the component up to date, the following activities should be performed regularly:

* Vulnerabilities fixing.
* RabbitMQ upgrade.
* Bug-fixing, improvement and feature implementation in operator, monitoring or other RabbitMQ components.

## Useful links

* [Installation guide](/docs/public/installation.md).
* [Troubleshooting guide](/docs/public/troubleshooting.md).
* [Internal Developer Guide](/docs/internal/developing.md).
* [Cloud INFRA Development process](https://bass.qubership.org/display/PLAT/Cloud+Infra+Platform+services%3A+development+process).
* [ArgoCD User guide](https://bass.qubership.org/display/PLAT/ArgoCD+guide)
