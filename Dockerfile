# Copyright © Michal Čihař <michal@weblate.org>
# SPDX-License-Identifier: GPL-3.0-or-later

FROM weblate/base:2025.38.0@sha256:7c0431ed338fe7159e284d588b8949b6bfc7eb9c4e66e7d7f7660dc1f8a6e0a4

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
    . /app/venv/bin/activate && \
    uv pip install --no-cache-dir -e /app/src

WORKDIR /home/weblate
USER weblate

ENTRYPOINT ["/app/venv/bin/wlc"]
