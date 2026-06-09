ARG BASE_IMAGE=library/rabbitmq:4.2.5-management-alpine

FROM ${BASE_IMAGE}

COPY docker-entrypoint.sh /usr/local/bin/
COPY scripts/get_user /bin/
COPY scripts/get_password /bin/
COPY scripts/change_password /bin/

ENV USER_UID=1000
ENV RABBITMQ_CONFIG_FILES=/opt/rabbitmq/conf.d
ENV RABBITMQ_ADVANCED_CONFIG_FILE=/opt/rabbitmq/conf.d/advanced.config
ENV RABBITMQ_ENABLED_PLUGINS_FILE=/opt/rabbitmq/conf.d/enabled_plugins

# Upgrade tools from edge to avoid vulnerabilities
RUN apk add --no-cache \
    --repository=https://dl-cdn.alpinelinux.org/alpine/edge/main \
    libssl3=3.5.7-r0 libcrypto3=3.5.7-r0

RUN set -x && apk upgrade --no-cache --available

RUN ln -sf /usr/local/bin/docker-entrypoint.sh && \
    mkdir -p /var/log/rabbitmq && \
    chmod -R 777 /var/log/rabbitmq && \
    chmod +x /bin/change_password && \
    chmod +x /bin/get_user && \
    chmod +x /bin/get_password && \
    chmod +x /usr/local/bin/docker-entrypoint.sh && \
    chmod -R a+r /opt/rabbitmq/plugins

COPY logging_definitions.json /opt/rabbitmq/

VOLUME /var/log/rabbitmq
VOLUME /tmp

ENTRYPOINT ["docker-entrypoint.sh"]

EXPOSE 4369 5671 5672 25672

USER ${USER_UID}

CMD ["rabbitmq-server"]