# Copyright © Michal Čihař <michal@weblate.org>
# SPDX-License-Identifier: GPL-3.0-or-later

FROM weblate/base:2025.19.0@sha256:99903c52a7aeb9e3f0046129419b7de74e64615e4cf76aa564c36d2f0ed5c383

LABEL name="wlc"
LABEL maintainer="Michal Čihař <michal@cihar.com>"
LABEL org.opencontainers.image.url="https://weblate.org/"
LABEL org.opencontainers.image.documentation="https://docs.weblate.org/en/latest/wlc.html"
LABEL org.opencontainers.image.source="https://github.com/WeblateOrg/wlc"
LABEL org.opencontainers.image.author="Michal Čihař <michal@weblate.org>"
LABEL org.opencontainers.image.vendor="Weblate"
LABEL org.opencontainers.image.title="wlc"
LABEL org.opencontainers.image.description="Command-line client for Weblate"
LABEL org.opencontainers.image.licenses="GPL-3.0-or-later"

COPY README.md LICENSE pyproject.toml /app/src/
COPY ./wlc/ /app/src/wlc

# This hack is widely applied to avoid python printing issues in docker containers.
# See: https://github.com/Docker-Hub-frolvlad/docker-alpine-python3/pull/13
ENV PYTHONUNBUFFERED=1

# hadolint ignore=SC1091
RUN \
    uv venv /app/venv && \
    source /app/venv/bin/activate && \
    uv pip install --no-cache-dir -e /app/src

WORKDIR /home/weblate
USER weblate

ENTRYPOINT ["/app/venv/bin/wlc"]
