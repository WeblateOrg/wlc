# Copyright © Michal Čihař <michal@weblate.org>
# SPDX-License-Identifier: GPL-3.0-or-later

FROM weblate/base:2026.34.0@sha256:433bcf285e06d2a078f77b1cb46d2697a66982d3eba8c7e9b65acf6b3533a6c6

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
