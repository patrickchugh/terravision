FROM alpine:3.23 AS base

ARG TERRAFORM_VERSION=1.10.5
ARG TARGETARCH=amd64

# Install required packages
RUN apk update && \
    apk add --no-cache git python3 py3-pip graphviz binutils curl unzip && \
    rm /usr/lib/python*/EXTERNALLY-MANAGED && \
    python3 -m ensurepip && \
    curl -fsSL "https://releases.hashicorp.com/terraform/${TERRAFORM_VERSION}/terraform_${TERRAFORM_VERSION}_linux_${TARGETARCH}.zip" -o /tmp/terraform.zip && \
    unzip /tmp/terraform.zip -d /usr/local/bin/ && \
    rm /tmp/terraform.zip && \
    addgroup -S -g 1000 terravision && \
    adduser -S -u 1000 -G terravision terravision && \
    rm -rf /root/.cache && \
    rm -rf /var/cache/apk/*

USER terravision

FROM base

ENV PATH=/home/terravision/.local/bin:$PATH

# Install terravision and dependencies
COPY --chown=terravision:terravision . /opt/terravision
RUN cd /opt/terravision && pip install .

USER root

RUN mkdir -p /project && \
    chown -R terravision:terravision /project

USER terravision

WORKDIR /project

ENTRYPOINT [ "terravision" ]
