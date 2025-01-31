FROM alpine:3.23 AS base

# Install required packages, create zser
RUN apk update && \
    apk add --no-cache git python3 py3-pip graphviz opentofu binutils && \
    rm /usr/lib/python*/EXTERNALLY-MANAGED && \
    python3 -m ensurepip && \
    addgroup -S -g 10000 terravision && \
    adduser -S -u 10000 -G terravision terravision && \
    rm -rf /root/.cache && \
    rm -rf /var/cache/apk/*

USER terravision

FROM base

# Install terravision
COPY --chown=terravision:terravision . /opt/terravision

WORKDIR /opt/terravision

RUN export PATH=$PATH:/home/terravision/.local/bin:/opt/terravision && \
    pip install -r requirements.txt && \
    ls -l && \
    chmod +x ./terravision

ENV PATH=$PATH:/opt/terravision

USER root

RUN ln -s ./terravision /usr/local/bin/terravision && \
    mkdir -p /project && \
    chown -R terravision:terravision /project
    
USER terravision

WORKDIR /project

ENTRYPOINT [ "terravision" ]
