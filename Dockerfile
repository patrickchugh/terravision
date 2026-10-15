# Terraform and tfenv are downloaded and checked in this stage; only the
# verified files reach the final image.
FROM alpine:3.23 AS verified-downloads

ARG TARGETARCH
# "latest" asks HashiCorp for the current release when the image is built.
# Pass --build-arg TERRAFORM_VERSION=1.x.y to pin one.
ARG TERRAFORM_VERSION=latest
# tfenv is pinned to the commit of a release, which a moved tag cannot change.
ARG TFENV_VERSION=v3.2.2
ARG TFENV_COMMIT=de6ce2e809c155cbc5e2cfeb3b1bef151244e045
# HashiCorp's release signing key, published at https://www.hashicorp.com/security.
# The only trust anchor: downloads must be signed by the key with this fingerprint.
ARG HASHICORP_KEY_FINGERPRINT=C874011F0AB405110D02105534365D9472D7468F

SHELL ["/bin/ash", "-eo", "pipefail", "-c"]

RUN apk add --no-cache curl git gnupg jq unzip

WORKDIR /verify

# Keep only the key with the pinned fingerprint, so a tampered key file
# cannot add a key of its own.
RUN export GNUPGHOME=/verify/gnupg && \
    mkdir -m 700 "$GNUPGHOME" && \
    curl -fsSL https://www.hashicorp.com/.well-known/pgp-key.txt | gpg --batch --quiet --import && \
    gpg --batch --export "$HASHICORP_KEY_FINGERPRINT" > hashicorp.gpg && \
    test -s hashicorp.gpg

RUN if [ "$TERRAFORM_VERSION" = latest ]; then \
        TERRAFORM_VERSION=$(curl -fsSL https://checkpoint-api.hashicorp.com/v1/check/terraform | jq -r .current_version); \
    fi && \
    echo "$TERRAFORM_VERSION" | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+(-[A-Za-z0-9.]+)?$' && \
    ARCH="${TARGETARCH:-$(uname -m | sed 's/x86_64/amd64/;s/aarch64/arm64/')}" && \
    RELEASE="https://releases.hashicorp.com/terraform/${TERRAFORM_VERSION}" && \
    ZIP="terraform_${TERRAFORM_VERSION}_linux_${ARCH}.zip" && \
    SUMS="terraform_${TERRAFORM_VERSION}_SHA256SUMS" && \
    curl -fsSLO "${RELEASE}/${ZIP}" && \
    curl -fsSLO "${RELEASE}/${SUMS}" && \
    curl -fsSLO "${RELEASE}/${SUMS}.72D7468F.sig" && \
    gpgv --keyring /verify/hashicorp.gpg "${SUMS}.72D7468F.sig" "${SUMS}" && \
    grep " ${ZIP}\$" "${SUMS}" | sha256sum -c - && \
    unzip -q "${ZIP}" terraform -d /verify/bin

# use-gpgv makes tfenv check each Terraform it installs against HashiCorp's
# signature, with gpgv and the key in ~/.gnupg/trustedkeys.gpg (copied below).
RUN git clone --quiet --depth 1 --branch "$TFENV_VERSION" https://github.com/tfutils/tfenv.git tfenv && \
    test "$(git -C tfenv rev-parse HEAD)" = "$TFENV_COMMIT" && \
    rm -rf tfenv/.git && \
    echo "binary: gpgv" > tfenv/use-gpgv

# Turns poetry.lock into a pip requirements file with a hash for every
# package, so the image installs exactly the locked, audited versions.
FROM alpine:3.23 AS locked-requirements

RUN apk add --no-cache python3 py3-pip && \
    python3 -m venv /poetry && \
    /poetry/bin/pip install --no-cache-dir poetry==2.3.2 poetry-plugin-export==1.10.1

WORKDIR /lock
COPY pyproject.toml poetry.lock ./
RUN /poetry/bin/poetry export --extras mcp --format requirements.txt --output requirements.txt

FROM alpine:3.23 AS base

# Install required packages (graphviz-dev needed for pygraphviz/graphviz2drawio)
RUN apk update && \
    apk add --no-cache git python3 graphviz graphviz-dev gcc musl-dev python3-dev binutils curl unzip bash gpgv && \
    rm /usr/lib/python*/EXTERNALLY-MANAGED && \
    python3 -m ensurepip && \
    addgroup -S -g 1000 terravision && \
    adduser -S -u 1000 -G terravision terravision && \
    rm -rf /root/.cache && \
    rm -rf /var/cache/apk/*

COPY --from=verified-downloads /verify/bin/terraform /usr/local/bin/terraform

USER terravision

FROM base

ENV PATH=/home/terravision/.local/bin:$PATH

USER root

COPY --from=verified-downloads /verify/tfenv /home/terravision/.tfenv
COPY --from=verified-downloads /verify/hashicorp.gpg /home/terravision/.gnupg/trustedkeys.gpg

# Install terravision and dependencies, with the [mcp] extra (MCP SDK and
# Pillow for inline previews) so `terravision mcp` works in the container
COPY --from=locked-requirements /lock/requirements.txt /tmp/requirements.txt
COPY --chown=terravision:terravision . /opt/terravision
WORKDIR /opt/terravision
# Dependencies come only from the lock file, and pip rejects any download
# whose hash differs; then terravision itself, without re-resolving them.
RUN python3 -m pip install --no-cache-dir --require-hashes -r /tmp/requirements.txt && \
    python3 -m pip install --no-cache-dir --no-deps . && \
    rm /tmp/requirements.txt && \
    mkdir -p /project && \
    chown -R terravision:terravision /project /home/terravision/.tfenv /home/terravision/.gnupg && \
    chmod 700 /home/terravision/.gnupg && \
    chmod u+x /opt/terravision/docker-entrypoint.sh

USER terravision

WORKDIR /project

ENTRYPOINT [ "/opt/terravision/docker-entrypoint.sh" ]
