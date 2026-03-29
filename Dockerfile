FROM alpine:3.23 AS base

ARG TARGETARCH

# Install required packages (graphviz-dev needed for pygraphviz/graphviz2drawio)
RUN apk update && \
    apk add --no-cache git python3 py3-pip graphviz graphviz-dev gcc musl-dev python3-dev binutils curl unzip bash jq && \
    rm /usr/lib/python*/EXTERNALLY-MANAGED && \
    python3 -m ensurepip && \
    ARCH="${TARGETARCH:-$(uname -m | sed 's/x86_64/amd64/;s/aarch64/arm64/')}" && \
    TF_VERSION=$(curl -s https://api.github.com/repos/hashicorp/terraform/releases/latest | jq -r '.tag_name' | sed 's/^v//') && \
    curl -fsSL "https://releases.hashicorp.com/terraform/${TF_VERSION}/terraform_${TF_VERSION}_linux_${ARCH}.zip" -o /tmp/terraform.zip && \
    unzip /tmp/terraform.zip -d /usr/local/bin/ && \
    rm /tmp/terraform.zip && \
    addgroup -S -g 1000 terravision && \
    adduser -S -u 1000 -G terravision terravision && \
    rm -rf /root/.cache && \
    rm -rf /var/cache/apk/*

USER terravision

FROM base

ENV PATH=/home/terravision/.local/bin:$PATH

USER root

# Install terravision and dependencies
COPY --chown=terravision:terravision . /opt/terravision
RUN cd /opt/terravision && \
    pip install . && \
    mkdir -p /project && \
    chown -R terravision:terravision /project && \
    git clone --depth=1 https://github.com/tfutils/tfenv.git /home/terravision/.tfenv && \
    chown -R terravision:terravision /home/terravision/.tfenv && \
    chmod u+x /opt/terravision/docker-entrypoint.sh

USER terravision

WORKDIR /project

ENTRYPOINT [ "/opt/terravision/docker-entrypoint.sh" ]
