
FROM ubuntu:16.04
MAINTAINER Kemele M. Endris <keme686@gmail.com>

USER root

#Python 3.5 installation
RUN apt-get update && \
    apt-get install -y --no-install-recommends  nano wget git curl  less psmisc && \
    apt-get install -y --no-install-recommends python3.5 python3-pip python3-setuptools && \
    pip3 install --upgrade pip

ADD . /BOUNCER

RUN cd /BOUNCER && pip3 install -r requirements.txt && \
    python3.5 setup.py install


RUN mkdir /data
WORKDIR /data

EXPOSE 5000

CMD ["tail", "-f", "/dev/null"]