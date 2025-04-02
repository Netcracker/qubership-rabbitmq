# SSL Configuration

You can enable TLS-based encryption for communication with RabbitMQ.

RabbitMQ uses Transport Layer Security (TLS) encryption across the cluster to verify authenticity of the servers and
clients that connect. RabbitMQ provides additional AQMP TLS port `5671`, while AQMP Plain port is `5672`, additional Management HTTPS port is `15671` and HTTP `15672`.

## SSL Configuration using pre created Secret with manually generated Certificates

1. Create secret with certificates :

    ```yaml
    kind: Secret
    apiVersion: v1
    metadata:
      name: ${SECRET_NAME}
      namespace: ${NAMESPACE}
    data:
      ca.crt: ${ROOT_CA_CERTIFICATE}
      tls.crt: ${CERTIFICATE}
      tls.key: ${PRIVATE_KEY}
    type: kubernetes.io/tls
    ```

    Where:
    * `${SECRET_NAME}` is the name of secret that contains all certificates. For example, `rabbitmq-tls-secret`.
    * `${NAMESPACE}` is the namespace where the secret should be created. For example, `rabbitmq-service`.
    * `${ROOT_CA_CERTIFICATE}` is the root CA in BASE64 format.
    * `${CERTIFICATE}` is the certificate in BASE64 format.
    * `${PRIVATE_KEY}` is the private key in BASE64 format.

2. Specify the following deployment parameters:

   ```yaml
   global:
      tls:
        enabled: true
        cipherSuites: []
        allowNonencryptedAccess: false
        generateCerts:
          enabled: false
          certProvider: helm
          durationDays: 365
          clusterIssuerName: ""
   rabbitmq:
      tls:
        enabled: true
        secretName: "rabbitmq-tls-secret"
        cipherSuites: []
        subjectAlternativeName:
          additionalDnsNames: []
          additionalIpAddresses: []
   ```

**NOTE:** For App Deployer, we need to use only `Rolling Update` mode because `Clean Install` mode deletes all pre-created secrets.

## SSL Configuration using CertManager

The example of deploy parameters to deploy RabbitMQ with enabled TLS and `CertManager` certificate generation:

```yaml
...
global:
  tls:
    enabled: true
    cipherSuites: []
    allowNonencryptedAccess: false
    generateCerts:
      enabled: true
      certProvider: cert-manager
      durationDays: 365
      clusterIssuerName: ""
rabbitmq:
  tls:
    enabled: true
    secretName: "rabbitmq-tls-secret"
    cipherSuites: []
    subjectAlternativeName:
      additionalDnsNames: []
      additionalIpAddresses: []
backupDaemon:
  tls:
    enabled: true
    secretName: "rabbitmq-backup-daemon-tls-secret"
    subjectAlternativeName:
      additionalDnsNames: [ ]
      additionalIpAddresses: [ ]
disasterRecovery:
  tls:
    enabled: true
    secretName: "rabbitmq-drd-tls-secret"
    cipherSuites: []
    subjectAlternativeName:
      additionalDnsNames: []
      additionalIpAddresses: []
...
```

Minimal parameters to enable TLS are:

```yaml
global:
  tls:
    enabled: true
    generateCerts:
      certProvider: cert-manager
...
```

## SSL Configuration using parameters with manually generated Certificates

You can automatically generate TLS-based secrets using Helm by specifying certificates in deployment parameters.

1. Following certificates should be generated in BASE64 format:

    ```yaml
    ca.crt: ${ROOT_CA_CERTIFICATE}
    tls.crt: ${CERTIFICATE}
    tls.key: ${PRIVATE_KEY}
    ```

     Where:
     * `${ROOT_CA_CERTIFICATE}` is the root CA in BASE64 format.
     * `${CERTIFICATE}` is the certificate in BASE64 format.
     * `${PRIVATE_KEY}` is the private key in BASE64 format.

2. Specify the certificates and other deployment parameters:

   ```yaml
    global:
      tls:
        enabled: true
        cipherSuites: []
        allowNonencryptedAccess: false
        generateCerts:
          enabled: false
          certProvider: helm
    rabbitmq:
      tls:
        enabled: true
        secretName: "rabbitmq-tls-secret"
        certificates:
          crt: LS0tLS1CRUdJTiBSU0E...  
          key: LS0tLS1CRUdJTiBSU0EgUFJJV...
          ca: LS0tLS1CRUdJTiBSU0E...
        cipherSuites: []
        subjectAlternativeName:
          additionalDnsNames: []
          additionalIpAddresses: []
    backupDaemon:
      tls:
        enabled: true
        certificates:
          crt: LS0tLS1CRUdJTiBSU0E...  
          key: LS0tLS1CRUdJTiBSU0EgUFJJV...
          ca: LS0tLS1CRUdJTiBSU0E...
        secretName: "rabbitmq-backup-daemon-tls-secret"
        subjectAlternativeName:
          additionalDnsNames: [ ]
          additionalIpAddresses: [ ]
    disasterRecovery:
      tls:
        enabled: true
        certificates:
          crt: LS0tLS1CRUdJTiBSU0E...  
          key: LS0tLS1CRUdJTiBSU0EgUFJJV...
          ca: LS0tLS1CRUdJTiBSU0E...
        secretName: "rabbitmq-drd-tls-secret"
        cipherSuites: []
        subjectAlternativeName:
          additionalDnsNames: []
          additionalIpAddresses: []
   ```

**Important**: If you have RabbitMQ installed with certificates generated via `CertManager` or with
manually created secret with certificates, remove these secrets before upgrading RabbitMQ with specified certificates.

## Certificate Renewal

CertManager automatically renews Certificates.
It calculates when to renew a Certificate based on the issued X.509 certificate's duration and a `renewBefore` value which specifies how long before expiry a certificate should be renewed.
By default, the value of `renewBefore` parameter is 2/3 through the X.509 certificate's `duration`. More info in [Cert Manager Renewal](https://cert-manager.io/docs/usage/certificate/#renewal).

After certificate renewed by CertManager the secret contains new certificate, but running applications store previous certificate in pods.
As CertManager generates new certificates before old expired the both certificates are valid for some time (`renewBefore`).

RabbitMQ service does not have any handlers for certificates secret changes, so you need to manually restart **all** RabbitMQ service pods until the time when old certificate is expired.

## Re-encrypt Route In Openshift Without NGINX Ingress Controller

Automatic re-encrypt Route creation is not supported out of box, need to perform the following steps:

1. Disable Ingress in deployment parameters: `rabbitmq.ingress.enabled: false`.

   Deploy with enabled rabbitmq Ingress leads to incorrect Ingress and Route configuration.

2. Create Route manually. You can use the following template as an example:

   ```yaml
   kind: Route
   apiVersion: route.openshift.io/v1
   metadata:
     annotations:
       route.openshift.io/termination: reencrypt
     name: <specify-uniq-route-name>
     namespace: <specify-namespace-where-rabbitmq-is-installed>
   spec:
     host: <specify-your-target-host-here>
     to:
       kind: Service
       name: rabbitmq 
       weight: 100
     port:
       targetPort: 15671-tcp
     tls:
       termination: reencrypt
       destinationCACertificate: <place-CA-certificate-here-from-rabbitmq-server-TLS-secret>
       insecureEdgeTerminationPolicy: Redirect
   ```

**NOTE**: If you can't access the rabbitmq host after Route creation because of "too many redirects" error, then one of the possible root
causes is there is HTTP traffic between balancers and the cluster. To resolve that issue it's necessary to add the Route name to
the exception list at the balancers,
[see documentation](https://git.qubership.org/PROD.Platform.HA/ocp-4-support/-/blob/master/documentation/Maintenance.md#configure-tls-offload-at-the-load-balancer-nodes)
