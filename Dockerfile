FROM alpine:3.21 AS base

# Install required packages, create zser
RUN apk update && \
    apk add --no-cache git python3 py3-pip graphviz opentofu binutils && \
    ln -s /usr/bin/tofu /usr/bin/terraform && \
    rm /usr/lib/python*/EXTERNALLY-MANAGED && \
    python3 -m ensurepip && \
    addgroup -S -g 1000 terravision && \
    adduser -S -u 1000 -G terravision terravision && \
    rm -rf /root/.cache && \
    rm -rf /var/cache/apk/*

USER terravision

FROM base

# Copy and Install terravision dependencies
COPY --chown=terravision:terravision requirements.txt /opt/terravision/requirements.txt

RUN export PATH=$PATH:/home/terravision/.local/bin && \
    cd /opt/terravision && \
    pip install -r requirements.txt

ENV PATH=$PATH:/opt/terravision

# Install terravision
COPY --chown=terravision:terravision . /opt/terravision

RUN chmod +x /opt/terravision/terravision

USER root

RUN mkdir -p /project && \
    chown -R terravision:terravision /project
    
USER terravision

WORKDIR /project

ENTRYPOINT [ "terravision" ]
