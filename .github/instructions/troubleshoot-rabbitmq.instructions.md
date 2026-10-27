---
description: >-
  Diagnostic playbook for RabbitMQ deployment, clustering, and runtime
  failures. Never invoke automatically — only when explicitly requested by
  the user.
applyTo: "**/*"
---

When diagnosing a RabbitMQ problem — Prometheus alert, pods not forming a
cluster, network partition, vhost down, queue corruption, memory/disk
alarm, .erlang.cookie or NFS errors, or a failed upgrade — apply the
`troubleshoot-rabbitmq` skill.
