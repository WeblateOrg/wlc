FROM python:3.8.6-alpine

COPY ./wlc/ LICENSE setup.cfg setup.py requirements.txt /app

# This hack is widely applied to avoid python printing issues in docker containers.
# See: https://github.com/Docker-Hub-frolvlad/docker-alpine-python3/pull/13
ENV PYTHONUNBUFFERED=1

RUN pip install -e /app/wlc

RUN useradd --create-home weblate
WORKDIR /home/weblate
USER weblate

ENTRYPOINT ["wlc"]
