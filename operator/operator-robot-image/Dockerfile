FROM ghcr.io/netcracker/qubership-docker-integration-tests:0.6.0

USER root

ENV ROBOT_OUTPUT=/opt/robot/output \
    SERVICE_CHECKER_SCRIPT=${ROBOT_HOME}/rabbitmq_pod_checker.py \
    SERVICE_CHECKER_SCRIPT_TIMEOUT=500 \
    USER_UID=1000

ENV STATUS_CUSTOM_RESOURCE_GROUP=apps
ENV STATUS_CUSTOM_RESOURCE_VERSION=v1
ENV STATUS_CUSTOM_RESOURCE_PLURAL=deployments
ENV STATUS_CUSTOM_RESOURCE_NAME=rabbitmq-integration-tests

RUN set -x && apk upgrade --no-cache --available

RUN mkdir -p ${ROBOT_HOME} \
    && mkdir -p ${ROBOT_OUTPUT}

RUN apk add --update --no-cache file gcc musl-dev libc6-compat zip gettext grep findutils wget sed jq

COPY requirements.txt ${ROBOT_HOME}/requirements.txt
COPY rabbitmq_pod_checker.py ${ROBOT_HOME}/rabbitmq_pod_checker.py
COPY robot ${ROBOT_HOME}

RUN set -x \
    && pip3 install "setuptools==80.10.1" \
    && pip3 install pbr \
    && pip3 install -r ${ROBOT_HOME}/requirements.txt \
    && apk add --no-cache curl \
    && rm -rf /var/cache/apk/*

RUN chown -R 1000:0 ${ROBOT_HOME} && chmod -R 775 ${ROBOT_HOME}

USER ${USER_UID}

WORKDIR ${ROBOT_HOME}
VOLUME /tmp
VOLUME /usr/bin
EXPOSE 8080
VOLUME ["${ROBOT_OUTPUT}"]
