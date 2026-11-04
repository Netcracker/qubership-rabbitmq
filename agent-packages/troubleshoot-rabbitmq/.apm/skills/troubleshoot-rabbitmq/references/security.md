This section provides information about the exposed ports, user accounts, password policies and password changing procedures in the RabbitMQ service.

## Exposed Ports

List of ports used by RabbitMQ and other Services.

| Port  | Service                      | Description                                                                                                                                                                                                                                                                                |
|-------|------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| 15672 | RabbitMQ                     | Port used for HTTP API clients, management UI and rabbitmqadmin, without TLS.                                                                                                                                                                                                              |
| 15671 | RabbitMQ                     | Port used for HTTP API clients, management UI and rabbitmqadmin, with TLS.                                                                                                                                                                                                                 |
| 4369  | RabbitMQ                     | Port used for epmd, a peer discovery service used by RabbitMQ nodes and CLI tools.                                                                                                                                                                                                         |
| 5671  | RabbitMQ                     | Port used by AMQP 0-9-1 and AMQP 1.0 clients with TLS.                                                                                                                                                                                                                                     |
| 5672  | RabbitMQ                     | Port used by AMQP 0-9-1 and AMQP 1.0 clients without TLS.                                                                                                                                                                                                                                  |
| 25672 | RabbitMQ                     | Port is used for inter-node and CLI tools communication.                                                                                                                                                                                                                                   |
| 15692 | RabbitMQ                     | Port used for Prometheus metrics.                                                                                                                                                                                                                                                          |
| 8443  | Backup Daemon                | Port is used for secure communication with the Backup Daemon service when TLS is enabled. This ensures encrypted and secure data transmission.                                                                                                                                             |
| 8080  | Backup Daemon                | Port used to manage and execute backup and restoration tasks to ensure data integrity and availability.                                                                                                                                                                                    |
| 8081  | Controller Manager           | Port is used for both liveness and readiness probes of the controller-manager container. The liveness probe checks the /healthz endpoint to ensure the container is alive, while the readiness probe checks the /readyz endpoint to determine if the container is ready to serve requests. |
| 8443  | DRD                          | If TLS for Disaster Recovery is enabled the HTTPS protocol and port 8443 is used for API requests to ensure secure communication.                                                                                                                                                          |
| 8080  | DRD                          | Port used for SiteManager endpoints.                                                                                                                                                                                                                                                       |
| 8080  | Integration-tests            | Exposes the container's port to the network. It allows access to the application running in the container.                                                                                                                                                                                 |
| 8000  | External RabbitMQ Monitoring | Exposes the container's port to the network. It allows access to the application running in the container.                                                                                                                                                                                 |
| 9096  | External RabbitMQ Monitoring | Port used for Prometheus metrics.                                                                                                                                                                                                                                                          |

## User Accounts

List of user accounts used for RabbitMQ and other Services.

| Service  | OOB accounts | Deployment parameter                            | Is Break Glass account | Can be blocked | Can be deleted | Comment                                                                                                                                                                                                                 |
|----------|--------------|-------------------------------------------------|------------------------|----------------|----------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| RabbitMQ | admin        | rabbitmq.custom_params.rabbitmq_default_user    | yes                    | no             | no             | The default admin user. There is no default value, the name must be specified during deploy.                                                                                                                            |

## Disabling User Accounts

RabbitMQ does not support disabling user accounts.

## Password Policies

* Passwords must be at least 8 characters long. This ensures a basic level of complexity and security.
* The passwords can contain only the following symbols:
    * Alphabets: a-zA-Z
    * Numerals: 0-9
    * Punctuation marks: ., ;, !, ?
    * Mathematical symbols: -, +, *, /, %
    * Brackets: (, ), {, }, <, >
    * Additional symbols: _, |, &, @, $, ^, #, ~

**Note**: To ensure that passwords are sufficiently complex, it is recommended to include:

* A minimum length of 8 characters
* At least one uppercase letter (A-Z)
* At least one lowercase letter (a-z)
* At least one numeral (0-9)
* At least one special character from the allowed symbols list

## Changing default password guide

Password changing procedures for RabbitMQ Service in this guide:

* [Password changing guide](/docs/public/maintenance.md#change-rabbitmq-default-password)

## Logging

Security events and critical operations should be logged for audit purposes. You can find more details about enabling
audit logging in [Audit guide](/docs/public/audit.md).
