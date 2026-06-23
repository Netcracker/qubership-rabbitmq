ARG BASE_IMAGE=library/rabbitmq:4.2.5-management-alpine

FROM ${BASE_IMAGE}

COPY docker-entrypoint.sh /usr/local/bin/
COPY scripts/get_user /bin/
COPY scripts/get_password /bin/
COPY scripts/change_password /bin/

ENV USER_UID=1000

# Upgrade tools from edge to avoid vulnerabilities
RUN echo "https://dl-cdn.alpinelinux.org/alpine/edge/main" > /etc/apk/repositories && \
    echo "https://dl-cdn.alpinelinux.org/alpine/edge/community" >> /etc/apk/repositories \
    && apk add --update --upgrade --no-cache \
        libssl3 libcrypto3

RUN set -x && apk upgrade --no-cache --available

RUN ln -sf usr/local/bin/docker-entrypoint.sh && \
    mkdir -p /var/log/rabbitmq && \
    chmod -R  777 /var/log/rabbitmq && \
    chmod -R  777 /etc/rabbitmq && \
    chmod +x /bin/change_password && \
    chmod +x /bin/get_user && \
    chmod +x /bin/get_password && \
    chmod +x /usr/local/bin/docker-entrypoint.sh && \
    chmod -R  a+r /opt/rabbitmq/plugins

COPY logging_definitions.json /etc/rabbitmq/

VOLUME /etc/rabbitmq
VOLUME /var/log/rabbitmq
VOLUME /tmp

ENTRYPOINT ["docker-entrypoint.sh"]

EXPOSE 4369 5671 5672 25672

USER ${USER_UID}

CMD ["rabbitmq-server"]
