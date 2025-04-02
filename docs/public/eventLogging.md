You can enable event logging for RabbitMQ.

RabbitMQ does not log events that occur with its entities (for example queues or exchanges).
Monitoring and auditing services can be interested in observing those events. RabbitMQ has a minimalistic mechanism for
event notifications that can be exposed to RabbitMQ clients with a plugin. This plugin is enabled by default.

The plugin gathers information about the following events:

1. **Queue, Exchange and Binding events**:
    * queue.deleted
    * queue.created
    * exchange.created
    * exchange.deleted
    * binding.created
    * binding.deleted

2. **Virtual host events**:
    * vhost.created
    * vhost.deleted

3. **User related events**:
    * user.created
    * user.deleted
    * user.password.changed

Plugin uses `amq.rabbitmq.event` exchange and following queues with corresponding bindings:

* rabbitmq.event.binding
* rabbitmq.event.exchange
* rabbitmq.event.queue
* rabbitmq.event.user
* rabbitmq.event.vhost

Queues store 100Mb of messages and message TTL is one week. Queues and exchange with bindings will be created in default virtual host (`/`).

To gather events from queues you can use following methods:

1. Using RabbitMQ management UI go to desired queue and get message using Ack mode `Nack message requeue true` (to prevent message deletion).
   You get message with information:

   ```txt
   Exchange	amq.rabbitmq.event
   Routing Key	queue.created
   arguments:	{<<"x-max-length-bytes">>,long,104857600}
   {<<"x-message-ttl">>,long,604800000}
   {<<"x-queue-type">>,longstr,<<"quorum">>}
   auto_delete:	false
   durable:	true
   exclusive:	false
   name:	rabbitmq.event.binding
   type:	rabbit_quorum_queue
   user_who_performed_action:	rmq-internal
   vhost:	/
   ```

   From this message you can get information about action, user who performed action and entity properties.

2. Using RabbitMQ management API with CURL command:

   ```sh
   curl -i -u USERNAME:PASSWORD -H "content-type:application/json" -X POST http://RABBITMQ_URL/api/queues/%2F/QUEUE_NAME/get -d '{"count":NUMBER_OF_MESSAGES,"ackmode":"ack_requeue_true","encoding":"auto"}'
   ```

   Example of response:

   ```json
   [
     {
       "payload_bytes": 0,
       "redelivered": true,
       "exchange": "amq.rabbitmq.event",
       "routing_key": "queue.created",
       "message_count": 2,
       "properties": {
         "timestamp": 1678793779,
         "delivery_mode": 2,
         "headers": {
           "arguments": [
             "{<<\"x-max-length-bytes\">>,long,104857600}",
             "{<<\"x-message-ttl\">>,long,604800000}",
             "{<<\"x-queue-type\">>,longstr,<<\"quorum\">>}"
           ],
           "auto_delete": false,
           "durable": true,
           "exclusive": false,
           "name": "rabbitmq.event.binding",
           "timestamp_in_ms": 1678793779714,
           "type": "rabbit_quorum_queue",
           "user_who_performed_action": "rmq-internal",
           "vhost": "/",
           "x-delivery-count": 3
         }
       },
       "payload": "",
       "payload_encoding": "string"
     }
   ]
   ```

3. Using rabbitmq CLI command from one of the RabbitMQ pods:

   `rabbitmqadmin get queue=QUEUE_NAME ackmode=ack_requeue_true count=NUMBER_OF_MESSAGES --user=USERNAME --password=PASSWORD`

   Example of response:

   ```text
   +---------------+--------------------+---------------+---------+---------------+------------------+-------------+
   |  routing_key  |      exchange      | message_count | payload | payload_bytes | payload_encoding | redelivered |
   +---------------+--------------------+---------------+---------+---------------+------------------+-------------+
   | queue.created | amq.rabbitmq.event | 2             |         | 0             | string           | True        |
   +---------------+--------------------+---------------+---------+---------------+------------------+-------------+
   ```

4. Set up RabbitMQ client (for example Python or Java client) and consume message from queues via AMQP port.
