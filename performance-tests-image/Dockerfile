FROM eclipse-temurin:21-jdk-alpine@sha256:0bfc69a4758a86710e5c474032d28400a8bd00874766f9e8b1642ac2fd293159

ADD https://github.com/rabbitmq/rabbitmq-perf-test/releases/download/v2.2.0/rabbitmq-perf-test-2.2.0-bin.tar.gz /PERFORMANCETEST/

RUN tar -xzf ./PERFORMANCETEST/rabbitmq-perf-test-2.2.0-bin.tar.gz -C ./PERFORMANCETEST && \
chmod -R 777 /PERFORMANCETEST && \
echo "alias perftest='bin/runjava -cp \"lib/*\" com.rabbitmq.perf.PerfTest'" >> ~/.bashrc
    

ENTRYPOINT ["sleep", "10000000"]
