# Copyright © Michal Čihař <michal@weblate.org>
# SPDX-License-Identifier: GPL-3.0-or-later

FROM weblate/base:2026.36.0@sha256:01fd63ac69e387ae184f214a40e34a3a316c44fa03cd5163e76b67039c0ea7b0

LABEL name="wlc"
LABEL maintainer="Michal Čihař <michal@weblate.org>"
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
    . /app/venv/bin/activate && \
    uv pip install --no-cache-dir -e /app/src

WORKDIR /home/weblate
# The user is defined in /etc/passwd as weblate, but UID is more reliable
USER 1000

ENTRYPOINT ["/app/venv/bin/wlc"]
