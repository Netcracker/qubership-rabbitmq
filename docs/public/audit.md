This chapter describes the security audit logging for RabbitMQ.

<!-- #GFCFilterMarkerStart# -->
The following topics are covered in this chapter:

[[_TOC_]]
<!-- #GFCFilterMarkerEnd# -->

# Common Information

Audit logs let you track key security events within RabbitMQ and are useful for compliance purposes or in the aftermath of a security breach.
You can find more detailed information about audit logs and their configuration in official documentation [RabbitMQ Audit Logging](https://www.rabbitmq.com/management.html#logging)

# Configuration

RabbitMQ audit logging is dependent on the `rabbitmq_management` plugin, which is enabled by default in the configuration.
For more information, see the [RabbitMQ Audit Log Documentation](https://www.rabbitmq.com/logging.html).

## Example of Events

The audit log format for events are described further:

### Crease Session

```text
2024-08-19 17:09:24.576684+00:00 [info] <0.47768665.0> connection <0.47768665.0> (10.131.111.15:44610 -> 10.131.110.237:5672) has a client-provided name: mistral-server:13:5487976e-fa05-424e-ad96-17b77a64de51
```

### Unauthenticated event

```text
2024-08-19 17:09:24.654203+00:00 [error] <0.47768651.0> AMQPLAIN login refused: user 'mistral_user' - invalid credentials
```

### Close session

```text
2024-08-20 05:46:34.047852+00:00 [warning] <0.53776392.0> closing AMQP connection <0.53776392.0> (10.131.111.15:48448 -> 10.131.110.237:5672):
```

### Unauthorized

```text
2024-08-20 05:57:49.606718+00:00 [warning] <0.53778050.0> HTTP access denied: user 'test' - User not authorised to access virtual host 
```

### Change Password

```text
2024-08-20 06:02:54.465245+00:00 [info] <0.53778723.0> Successfully changed password for user 'test'
```

### CRUD users

```text
2024-08-20 06:04:11.655718+00:00 [info] <0.53778987.0> Created user 'test2'
```

### Modify Grants

```text
2024-08-20 06:07:10.086294+00:00 [info] <0.53779425.0> Successfully set permissions for user 'test2' in virtual host '/' to '.*', '.*', '.*'
```
