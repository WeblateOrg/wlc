FROM python:3.10.5-alpine

LABEL name="wlc"
LABEL maintainer="Michal Čihař <michal@cihar.com>"
LABEL org.opencontainers.image.url="https://weblate.org/"
LABEL org.opencontainers.image.documentation="https://docs.weblate.org/en/latest/wlc.html"
LABEL org.opencontainers.image.source="https://github.com/WeblateOrg/wlc"
LABEL org.opencontainers.image.vendor="Michal Čihař"
LABEL org.opencontainers.image.title="wlc"
LABEL org.opencontainers.image.description="Command-line client for Weblate"
LABEL org.opencontainers.image.licenses="GPL-3.0-or-later"

COPY README.md LICENSE setup.cfg setup.py requirements.txt /app/
COPY ./wlc/ /app/wlc

# This hack is widely applied to avoid python printing issues in docker containers.
# See: https://github.com/Docker-Hub-frolvlad/docker-alpine-python3/pull/13
ENV PYTHONUNBUFFERED=1

RUN pip install --no-cache-dir -e /app && adduser -S weblate

WORKDIR /home/weblate
USER weblate

ENTRYPOINT ["wlc"]
