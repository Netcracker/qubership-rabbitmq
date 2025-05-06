This chapter describes the overview and architectural features of RabbitMQ.

<!-- #GFCFilterMarkerStart# -->
[[_TOC_]]
<!-- #GFCFilterMarkerEnd# -->

# Overview

[RabbitMQ]((https://www.rabbitmq.com/documentation.html)) is a widely used open-source message broker that provides a robust and reliable messaging system for applications.
It plays a crucial role in modern software architectures by enabling asynchronous communication between different components and systems.

The necessity of RabbitMQ arises from its ability to decouple the sending and receiving of messages, allowing applications to scale independently and ensuring reliable message delivery.
It supports various messaging patterns, such as point-to-point, publish/subscribe, and request/reply, making it versatile for different communication scenarios.

From a business perspective, RabbitMQ offers several benefits.

Firstly, it enhances system reliability by providing fault-tolerant message handling and ensuring message delivery even in the face of failures.
This improves the overall application resilience and minimizes the risk of data loss.

Secondly, RabbitMQ enables flexible and scalable architectures, allowing businesses to easily add or remove application components as per their evolving needs.

Additionally, its support for different programming languages and protocols promotes interoperability and integration across diverse technology stacks.

## RabbitMQ Delivery and Features

The platform provides RabbitMQ deployment to Kubernetes/OpenShift using its own helm chart with operator and additional features.
The deployment procedure and additional features include the following:

* Backup and restore for users, queues, and exchanges configurations.
  For more information, refer to [RabbitMQ Operator Maintenance](/docs/public/maintenance.md#backup-and-recovery) in _Cloud Platform Maintenance Guide_.
* Monitoring integration with Grafana Dashboard and Prometheus Alerts.
  For more information, refer to [RabbitMQ Operator Service Monitoring](/docs/public/monitoring.md) in _Cloud Platform Monitoring Guide_.
* Disaster Recovery scheme with entity configurations' replication.
  For more information, refer to [RabbitMQ Disaster Recovery](/docs/public/disasterRecovery.md) in _Cloud Platform Disaster Recovery Guide_.

# RabbitMQ Components

The following image shows the various RabbitMQ components.  

![Application overview](/docs/public/images/rabbitmq_components_overview.drawio.png)

## RabbitMQ Operator

RabbitMQ Operator is a microservice designed specifically for Kubernetes environments.
It simplifies the deployment and management of RabbitMQ clusters, which are critical for distributed coordination.
In addition to deploying the RabbitMQ cluster, the operator also takes care of managing supplementary services, ensuring seamless integration and efficient resource utilization.
With the RabbitMQ Operator, administrators can easily maintain and scale their RabbitMQ infrastructure,
focusing on other important aspects of their applications without worrying about the intricacies of cluster management.

In addition, the RabbitMQ Operator performs disaster recovery logic and orchestrates RabbitMQ switchover and failover operations.

## RabbitMQ

RabbitMQ is a custom distribution of the original RabbitMQ adapted for the cloud environment, offering additional features and tools for enhanced functionality and management.
This container provides the flexibility to configure RabbitMQ according to various deployment types and configurations.
It also incorporates logging capabilities to capture and analyze important system events and out-of-the-box Prometheus exporters for metrics.
Additionally, it incorporates health check functionalities and other tools, streamlining the monitoring and maintenance of RabbitMQ clusters.
RabbitMQ, by default, includes a management plugin with a user interface (UI) that simplifies RabbitMQ administration tasks,
enabling efficient management of RabbitMQ clusters through a comprehensive and intuitive interface.

## RabbitMQ Backup Daemon

RabbitMQ Backup Daemon is a microservice that offers a convenient REST API for performing backups and restores of RabbitMQ users, queues, and exchanges' configurations.
It enables users to initiate backups and restores programmatically, making it easier to automate these processes.
Additionally, the daemon allows users to schedule regular backups, ensuring data protection and disaster recovery.
Furthermore, it offers the capability to store backups on remote S3 storage, providing a secure and scalable solution for long-term data retention.

## Telegraf Agent (External RabbitMQ Only)

The RabbitMQ Telegraf Agent microservice is built on the Telegraf framework, specializing in collecting and analyzing metrics from an external RabbitMQ, such as AmazonMQ,
when usual ways of getting metrics from Prometheus plugin are not available.
It seamlessly integrates with RabbitMQ clusters, capturing essential data points for performance monitoring and analysis.
Additionally, the microservice provides a Grafana dashboard, offering a comprehensive visualization of RabbitMQ metrics for better insights and diagnostics.

# Supported Deployment Schemes

## On-Prem

### HA Deployment Scheme

The following image shows the RabbitMQ HA deployment scheme.

![HA scheme](/docs/public/images/rabbitmq_on_prem_deploy.drawio.png)

From the above image, the main features of the RabbitMQ K8s deployment are:

* The minimal number of replicas for HA scheme of RabbitMQ is 3.
* RabbitMQ pods are distributed through Kubernetes nodes and availability zones based on affinity policy during the deployment.
* Each RabbitMQ pod has its own Persistent Volume storage.
* In addition to RabbitMQ main storage, the RabbitMQ Backup Daemon pod has its own Persistent Volume for backups.
* Some components are deployed by the RabbitMQ Operator. The RabbitMQ Operator itself is deployed by Helm.

#### Single StatefulSet Deployment

The following image shows a typical RabbitMQ Single-StatefulSet Deployment architecture with persistent storage and three RabbitMQ replicas.

![Typical Single-StatefulSet Deployment Architecture with Three Pods](/docs/public/images/RabbitMQSingleSSDeployment.png)

This configuration is used for the following storage types: `PersistentVolume Provisioner`, `Autodiscovery PVs`, and `Non-persistent Storage`.
The RabbitMQ autocluster plugin is always enabled since it is required for RabbitMQ to form a cluster in this deployment scheme.
In this configuration, the pods usually are not bound to nodes, unless the region is specified.
The region can bind the StatefulSet (and therefore all RabbitMQ pods in this configuration) to a set of physical nodes.

#### Multi-StatefulSet Deployment

The following image shows the typical RabbitMQ Multi-StatefulSet Deployment architecture with three RabbitMQ replicas.

![Typical Multi-StatefulSet Deployment Architecture with Three Pods](/docs/public/images/RabbitMQMultiSSDeployment.png)

This configuration is used for the following storage types: `Host bound PVs`, `Pre-created PVCs`, and `Host Bound PVs with Node Names`.
Every pod is created in a different StatefulSet, and every pod is always bound to a separate physical node.
In this configuration, a pod always starts on the same node as it was running on previously.
The RabbitMQ autocluster plugin is not needed in this deployment option.

### Non-HA Deployment Scheme

For a non-HA deployment scheme, it is possible to use one pod of the RabbitMQ cluster.

### DR Deployment Scheme

The following image shows the RabbitMQ DR deplyment scheme.

![DR scheme](/docs/public/images/rabbitmq_dr_deploy.drawio.png)

In RabbitMQ, the scheme for disaster recovery is replication of user, queue, and exchange configurations through backup and restore operations during switchover and failover (blue arrows).

For more information, refer to [RabbitMQ Disaster Recovery](/docs/public/disasterRecovery.md) in _Cloud Platform Disaster Recovery Guide_.

## Integration With Managed Services

### Google Cloud

Not applicable; the default HA scheme is used for deployment to Google Cloud.

### AWS AmazonMQ

RabbitMQ allows you to deploy RabbitMQ supplementary services, like Monitoring and Backup Daemon, using AmazonMQ for RabbitMQ connection, without deploying the RabbitMQ server.
Thus, the features and functions of these services are adopted to AmazonMQ and available for Kafka delivery.

![AWS Scheme](/docs/public/images/rabbitmq_aws_deploy.drawio.png)

For more information, refer to [Deploying Side Services Using AmazonMQ](/docs/public/managed/amazon/README.md).

### Azure

Not applicable; the default HA scheme is used for the deployment to Azure.
