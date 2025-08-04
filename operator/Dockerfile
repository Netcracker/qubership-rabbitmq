FROM python:3.12.11-alpine3.22

ENV WORKDIR=/opt/operator/ \
    USER_UID=1000 \
    USER_NAME=rabbitmq-operator

COPY build/requirements.txt requirements.txt
COPY src/handler.py ${WORKDIR}
COPY src/rabbitconstants.py ${WORKDIR}
COPY src/rabbit_helper.py ${WORKDIR}
COPY src/backup_helper.py ${WORKDIR}
COPY src/exceptions.py ${WORKDIR}
COPY src/velero_delete_pods_rmqlocal.py ${WORKDIR}
COPY build/user_setup /usr/local/bin
COPY build/entrypoint /usr/local/bin

RUN apk add --update --no-cache bash build-base apk-tools

RUN pip install --upgrade pip setuptools==80.9.0  && pip install -r requirements.txt

RUN chmod 777 /usr/local/bin/user_setup && \
chmod 777 /usr/local/bin/entrypoint && \
chmod 777 /opt/operator/rabbitconstants.py && \
chmod 777 /opt/operator/rabbit_helper.py && \
chmod 777 /opt/operator/handler.py && \
chmod 777 /opt/operator/velero_delete_pods_rmqlocal.py
RUN /usr/local/bin/user_setup

# Upgrade all tools to avoid vulnerabilities
RUN set -x && apk upgrade --no-cache --available --force-missing-repositories

ENTRYPOINT ["/usr/local/bin/entrypoint"]

CMD ["sh", "-c", "kopf run -n ${WATCH_NAMESPACE} --liveness=http://0.0.0.0:8081/healthz --standalone /opt/operator/handler.py"]

USER ${USER_UID}
