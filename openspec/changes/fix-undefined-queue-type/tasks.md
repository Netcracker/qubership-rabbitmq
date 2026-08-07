## 1. Helm Chart — rabbitmq.conf default_queue_type

- [x] 1.1 Add `rabbitmq.setDefaultQueueTypeClassic` boolean to `operator/charts/helm/rabbitmq/values.yaml` with default `true` and a comment explaining it guards the queue-type remediation feature
- [x] 1.2 In `operator/charts/helm/rabbitmq/templates/_helpers.tpl`, inside `rabbitmq.clusterConfiguration`, add a guarded line: `{{- if .Values.rabbitmq.setDefaultQueueTypeClassic }}` / `default_queue_type = classic` / `{{- end }}`
- [ ] 1.3 Verify that `helm template` renders `default_queue_type = classic` in the resulting ConfigMap when the toggle is `true`, and that the line is absent when `false`

## 2. Helm Chart — Operator env var injection

- [x] 2.1 In the operator Deployment template (or the values section that builds its env), inject env var `RABBITMQ_SET_DEFAULT_QUEUE_TYPE_CLASSIC` from the same `rabbitmq.setDefaultQueueTypeClassic` Helm value (map `true`→`"true"`, `false`→`"false"`)
- [ ] 2.2 Verify the env var appears in the rendered Deployment manifest with the expected value

## 3. Operator — Remediation helper functions

- [x] 3.1 In `operator/src/handler.py`, add a helper function `remediate_vhost_queue_types(kubernetes_helper, pod_name)` that calls `exec_command_in_pod` with the vhost eval script (iterate vhosts, set `default_queue_type = classic` where unset or `"undefined"`). To set default_queue_type run script:
```
rabbitmqctl eval '
lists:foreach(
  fun(VHostName) ->
    VHost = rabbit_vhost:lookup(VHostName),
    Meta = vhost:get_metadata(VHost),
    case maps:get(default_queue_type, Meta, undefined) of
      undefined ->
        rabbit_db_vhost:merge_metadata(VHostName, #{default_queue_type => <<"classic">>}),
        io:format("Set DQT for virtual host ~p (was not set)~n", [VHostName]);
      <<"undefined">> ->
        rabbit_db_vhost:merge_metadata(VHostName, #{default_queue_type => <<"classic">>}),
        io:format("Set DQT for virtual host ~p (was <<\"undefined\">>)~n", [VHostName]);
      DQT ->
        io:format("Virtual host ~p already has DQT = ~p~n", [VHostName, DQT])
    end
  end,
  rabbit_vhost:list_names()),
ok.
'
```
- [x] 3.2 Add a helper function `remediate_queue_types(kubernetes_helper, pod_name)` that calls `exec_command_in_pod` with the queue eval script (iterate all queues, set `x-queue-type = classic` where absent or `"undefined"`). To set x-queue-type run script:
rabbitmqctl eval '
lists:foreach(
  fun(Q) ->
    QName = amqqueue:get_name(Q),
    Args = amqqueue:get_arguments(Q),
    case rabbit_misc:table_lookup(Args, <<"x-queue-type">>) of
      undefined ->
        NewArgs = rabbit_misc:set_table_value(Args, <<"x-queue-type">>, longstr, <<"classic">>),
        rabbit_db_queue:update(QName, fun(Q0) -> amqqueue:set_arguments(Q0, NewArgs) end),
        io:format("Set x-queue-type for ~p to <<\"classic\">> (was not set)~n", [QName]);
      {longstr, <<"undefined">>} ->
        NewArgs = rabbit_misc:set_table_value(Args, <<"x-queue-type">>, longstr, <<"classic">>),
        rabbit_db_queue:update(QName, fun(Q0) -> amqqueue:set_arguments(Q0, NewArgs) end),
        io:format("Set x-queue-type for ~p to <<\"classic\">> (was <<\"undefined\">>)~n", [QName]);
      {_Type, Val} ->
        io:format("Queue ~p already has x-queue-type = ~p~n", [QName, Val])
    end
  end,
  rabbit_amqqueue:list()),
ok.
'
- [x] 3.3 Add a helper `get_primary_rabbitmq_pod(kubernetes_helper)` (or reuse the existing pod-selection logic) that returns the name of the first Running pod in the RabbitMQ StatefulSet

## 4. Operator — Kopf timer handler

- [x] 4.1 Register a `@kopf.timer` handler named `queue_type_remediation` with `interval=86400` and `initial_delay=0`, gated on `os.environ.get("RABBITMQ_SET_DEFAULT_QUEUE_TYPE_CLASSIC", "true") == "true"`
- [x] 4.2 Inside the handler, call `get_primary_rabbitmq_pod`, then call `remediate_vhost_queue_types` and `remediate_queue_types` in sequence; log results and catch exceptions so a failure is non-fatal and Kopf reschedules the next run normally
- [x] 4.3 Ensure the timer decorator targets the correct CRD group/version/plural so it fires once per cluster (not once per CR replica), mirroring the pattern of the existing `shovel_monitoring` timer

## 5. Validation

- [ ] 5.1 Deploy to a test cluster with a mix of vhosts/queues: some with explicit type, some with no type, some with `x-queue-type=undefined`; confirm the operator log shows correct per-resource output and only `undefined`/unset entries are patched
- [ ] 5.2 Run a backup after remediation and confirm the exported JSON contains no `"undefined"` queue-type values
- [ ] 5.3 Set `rabbitmq.setDefaultQueueTypeClassic=false`, re-deploy, and confirm neither the `default_queue_type` config line nor the timer handler fires
- [ ] 5.4 Trigger an operator restart on a clean cluster and confirm the timer fires at startup (initial_delay=0) without waiting 24 hours
