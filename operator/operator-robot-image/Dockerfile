FROM ghcr.io/netcracker/qubership-docker-integration-tests:0.1.19

ENV ROBOT_OUTPUT=${ROBOT_HOME}/output\
    SERVICE_CHECKER_SCRIPT=${ROBOT_HOME}/rabbitmq_pod_checker.py \
    USER_UID=1000

ENV STATUS_CUSTOM_RESOURCE_GROUP=apps
ENV STATUS_CUSTOM_RESOURCE_VERSION=v1
ENV STATUS_CUSTOM_RESOURCE_PLURAL=deployments
ENV STATUS_CUSTOM_RESOURCE_NAME=rabbitmq-integration-tests

# Upgrade tools from edge to avoid vulnerabilities
RUN echo "https://dl-cdn.alpinelinux.org/alpine/edge/main" > /etc/apk/repositories && \
    echo "https://dl-cdn.alpinelinux.org/alpine/edge/community" >> /etc/apk/repositories \
    && apk add --update --upgrade --no-cache \
        libssl3 libcrypto3

RUN set -x && apk upgrade --no-cache --available

RUN mkdir -p ${ROBOT_HOME} \
    && mkdir -p ${ROBOT_OUTPUT}

RUN apk add --update file gcc musl-dev libc6-compat zip jq gettext grep findutils wget sed \
    && pip3 install setuptools==80.9.0

COPY rabbitmq_pod_checker.py ${ROBOT_HOME}/rabbitmq_pod_checker.py
COPY requirements.txt requirements.txt

RUN pip install pbr && \
    pip install -r requirements.txt

COPY robot ${ROBOT_HOME}

WORKDIR ${ROBOT_HOME}

VOLUME /tmp
VOLUME /usr/bin

USER ${USER_UID}

# Expose the port
EXPOSE 8080
VOLUME ["${ROBOT_OUTPUT}"]
