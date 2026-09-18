FROM eclipse-temurin:21-jdk-alpine@sha256:cd87715a8d45cfaa42419207c64680234f62785c49055cccd20437b5c9018380

ADD https://github.com/rabbitmq/rabbitmq-perf-test/releases/download/v2.2.0/rabbitmq-perf-test-2.2.0-bin.tar.gz /PERFORMANCETEST/

RUN tar -xzf ./PERFORMANCETEST/rabbitmq-perf-test-2.2.0-bin.tar.gz -C ./PERFORMANCETEST && \
chmod -R 777 /PERFORMANCETEST && \
echo "alias perftest='bin/runjava -cp \"lib/*\" com.rabbitmq.perf.PerfTest'" >> ~/.bashrc
    

ENTRYPOINT ["sleep", "10000000"]
