FROM python:3.8.6-alpine

COPY LICENSE setup.cfg setup.py requirements.txt /app/
COPY ./wlc/ /app/wlc

# This hack is widely applied to avoid python printing issues in docker containers.
# See: https://github.com/Docker-Hub-frolvlad/docker-alpine-python3/pull/13
ENV PYTHONUNBUFFERED=1

RUN pip install -e /app

RUN adduser -S weblate
WORKDIR /home/weblate
USER weblate

ENTRYPOINT ["wlc"]
