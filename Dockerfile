FROM alpine:3.23 AS base

ARG TERRAFORM_VERSION=1.10.5
ARG TARGETARCH

# Install required packages (graphviz-dev needed for pygraphviz/graphviz2drawio)
RUN apk update && \
    apk add --no-cache git python3 py3-pip graphviz graphviz-dev gcc musl-dev python3-dev binutils curl unzip && \
    rm /usr/lib/python*/EXTERNALLY-MANAGED && \
    python3 -m ensurepip && \
    ARCH="${TARGETARCH:-$(uname -m | sed 's/x86_64/amd64/;s/aarch64/arm64/')}" && \
    curl -fsSL "https://releases.hashicorp.com/terraform/${TERRAFORM_VERSION}/terraform_${TERRAFORM_VERSION}_linux_${ARCH}.zip" -o /tmp/terraform.zip && \
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
