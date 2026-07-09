FROM ghcr.io/netcracker/qubership-docker-integration-tests:0.5.6

USER root

ENV ROBOT_OUTPUT=/opt/robot/output \
    SERVICE_CHECKER_SCRIPT=${ROBOT_HOME}/rabbitmq_pod_checker.py \
    SERVICE_CHECKER_SCRIPT_TIMEOUT=500 \
    USER_UID=1000

ENV STATUS_CUSTOM_RESOURCE_GROUP=apps
ENV STATUS_CUSTOM_RESOURCE_VERSION=v1
ENV STATUS_CUSTOM_RESOURCE_PLURAL=deployments
ENV STATUS_CUSTOM_RESOURCE_NAME=rabbitmq-integration-tests

# Upgrade tools from edge to avoid vulnerabilities
RUN apk add --no-cache \
    --repository=https://dl-cdn.alpinelinux.org/alpine/edge/main \
    libssl3=3.5.7-r0 libcrypto3=3.5.7-r0

RUN set -x && apk upgrade --no-cache --available

RUN mkdir -p ${ROBOT_HOME} \
    && mkdir -p ${ROBOT_OUTPUT}

RUN set -x && apk upgrade --no-cache --available

RUN apk add --update file gcc musl-dev libc6-compat zip gettext grep findutils wget sed \
    --repository=https://dl-cdn.alpinelinux.org/alpine/edge/main \
    jq=1.8.2-r0

COPY requirements.txt ${ROBOT_HOME}/requirements.txt
COPY rabbitmq_pod_checker.py ${ROBOT_HOME}/rabbitmq_pod_checker.py
COPY robot ${ROBOT_HOME}

RUN set -x \
    && pip3 install "setuptools==80.10.1" \
    && pip3 install pbr \
    && pip3 install -r ${ROBOT_HOME}/requirements.txt \
    && apk add --no-cache \
        --repository=https://dl-cdn.alpinelinux.org/alpine/edge/main \
        curl=8.21.0-r0 libcurl=8.21.0-r0 \
    && rm -rf /var/cache/apk/*

RUN chown -R 1000:0 ${ROBOT_HOME} && chmod -R 775 ${ROBOT_HOME}

USER ${USER_UID}

WORKDIR ${ROBOT_HOME}
VOLUME /tmp
VOLUME /usr/bin
EXPOSE 8080
VOLUME ["${ROBOT_OUTPUT}"]
