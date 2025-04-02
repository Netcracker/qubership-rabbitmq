# Developer Guide

## Dev-Kit

### JSON Schema

The Values JSON Schema is file which defines the structure of data that can be placed in `values.yaml`.

To generate or validate JSON Schema need to use [Netcracker values-schema generator](https://git.qubership.org/Personal.Streaming.Platform/values-schema-generator).

The developer should install it on the host machine using [command line option](https://git.qubership.org/Personal.Streaming.Platform/values-schema-generator#command-line).

When generator is installed, then developer can use the following scripts:

* `make_json_schema.sh` - generates JSON Schema, which is placed in `operator/charts/helm/rabbitmq` directory.
* `json_schema_linter.sh` - runs generator in linter mode to validate current JSON Schema.
