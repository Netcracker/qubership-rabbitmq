#!/usr/bin/env bash

echo "TEST_PATH = ${TEST_PATH}"

oc create sa rabbitmq || true
oc policy add-role-to-user admin -z rabbitmq

if [[ -z "${OPENSHIFT_TOKEN}" ]];
then
    OPENSHIFT_TOKEN=$(oc whoami -t)
fi

FIXED_CLOUD_URL=$(echo "${CLOUD_URL}" | cut -d'/' -f3 | cut -d':' -f1)

oc delete secrets rabbit-tests --ignore-not-found
oc create secret generic rabbit-tests \
    --from-literal=openshift_workspace="${OPENSHIFT_WORKSPACE}" \
    --from-literal=openshift_user="${OPENSHIFT_USER}" \
    --from-literal=openshift_password="${OPENSHIFT_PASSWORD}" \
    --from-literal=openshift_token="${OPENSHIFT_TOKEN}" \
    --from-literal=cloud_url="${FIXED_CLOUD_URL}" \
    --from-literal=rmquser="${RABBITMQ_USER}" \
    --from-literal=rmqpassword="${RABBITMQ_PASSWORD}"
# shellcheck disable=SC1078
echo "kind: Template
apiVersion: v1
metadata:
  name: rabbit-tests-template
  annotations:
    openshift.io/display-name: Rabbit test template
    description: Template for rabbit test
labels:
  template: rabbit-tests-template
parameters:
- name: TESTIMAGE
- name: TEST_TYPE
objects:
  - apiVersion: v1
    kind: DeploymentConfig
    metadata:
      name: rabbit-tests
      labels:
        app: rabbit-tests
    spec:
      strategy:
        type: Rolling
        rollingParams:
          updatePeriodSeconds: 1
          intervalSeconds: 1
          timeoutSeconds: 600
      triggers:
        - type: ConfigChange
      replicas: 1
      selector:
        app: rabbit-tests
        deploymentconfig: rabbit-tests
        name: rabbit-tests
      template:
        metadata:
          labels:
            app: rabbit-tests
            deploymentconfig: rabbit-tests
            name: rabbit-tests
        spec:
          serviceAccountName: rabbitmq
          containers:
            - name: rabbit-tests
              image: ${TEST_PATH}
              imagePullPolicy: Always
              env:
                - name: MT_rabbit_URL
                  value: http://rabbit:8989/v2
                - name: OPENSHIFT_WORKSPACE
                  valueFrom:
                    fieldRef:
                      fieldPath: metadata.namespace
                - name: RMQUSER
                  valueFrom:
                    secretKeyRef:
                      name: rabbit-tests
                      key: rmquser
                - name: RMQPASSWORD
                  valueFrom:
                    secretKeyRef:
                      name: rabbit-tests
                      key: rmqpassword
                - name: MT_OWN_URL
                  value: http://rabbit-tests:8080
                - name: OPENSHIFT_USER
                  valueFrom:
                    secretKeyRef:
                      name: rabbit-tests
                      key: openshift_user
                - name: OPENSHIFT_PASSWORD
                  valueFrom:
                    secretKeyRef:
                      name: rabbit-tests
                      key: openshift_password
                - name: OPENSHIFT_TOKEN
                  valueFrom:
                    secretKeyRef:
                      name: rabbit-tests
                      key: openshift_token
                - name: CLOUD_URL
                  valueFrom:
                    secretKeyRef:
                      name: rabbit-tests
                      key: cloud_url
                - name: NAMESPACE
                  valueFrom:
                    fieldRef:
                      fieldPath: metadata.namespace
                - name: TEST_TYPE
                  value: cluster
                - name: TESTIMAGE
                  value: ${TEST_PATH}
              resources:
                limits:
                  cpu: 100m
                  memory: 200Mi
                requests:
                  cpu: 100m
                  memory: 200Mi
              imagePullPolicy: Always
" | oc process -p TESTIMAGE="${TESTIMAGE}" TEST_TYPE="${TEST_TYPE}" -f - | oc apply -f -

ATTEMPTS=108
SLEEP_BETWEEN_ITERATIONS=5

echo "Timeout is $((ATTEMPTS * SLEEP_BETWEEN_ITERATIONS)) seconds"

error_handling() {
    echo "Read tests logs:"

    oc logs dc/rabbit-tests

    exit 1
}

sleep 30

for i in $(seq 1 ${ATTEMPTS});
do
  echo "Sleeping the ${i} times..."
  sleep ${SLEEP_BETWEEN_ITERATIONS}

  if [ "${i}" -eq "${ATTEMPTS}" ]
  then
      echo "Time is over"

      error_handling
  fi

  NUMBER_OF_RESULT_FILES="$(timeout 15s oc rsh dc/rabbit-tests /bin/sh -c 'ls ./target | wc -l' || true)"

  echo "The result of command is ${NUMBER_OF_RESULT_FILES}"

  case "${NUMBER_OF_RESULT_FILES}" in
        "3")
            echo "Job is succeeded"
            break
            ;;
        *)
            echo "Tests are running"
            ;;
  esac
done

echo "Read tests logs:"
oc logs dc/rabbit-tests

rm -rf target
mkdir target

TEST_POD_NAME=$(oc get pods -o=jsonpath='{range .items[*]}{.metadata.name}{"\n"}{end}' | grep rabbit-tests | grep -v deploy)
oc rsync "${TEST_POD_NAME}:/robot-tests/target" ./

if grep -q "pass=\"1\" fail=\"0\"" target/output.xml; then
    echo "CLUSTER TEST PASSED"
else
    echo "CLUSTER TEST FAILED"
    exit 1
fi

if [[ "${TEST_TYPE}" = "all" ]] || [[ "${TEST_TYPE}" = "deployment" ]];
then
    oc delete project "${DEPLOY_WORKSPACE}"
fi
oc delete all -l app=rabbit-tests --ignore-not-found