#!/bin/sh -xe

# This script starts docker and systemd on el7

docker run --privileged -d -ti -e "container=docker"  -v /sys/fs/cgroup:/sys/fs/cgroup -v `pwd`:/akroma-masternode-managememt:rw  centos:centos${OS_VERSION}   /usr/sbin/init
DOCKER_CONTAINER_ID=$(docker ps | grep centos | awk '{print $1}')
docker logs $DOCKER_CONTAINER_ID
docker exec -ti $DOCKER_CONTAINER_ID /bin/bash -xec "yum install epel-release yum install gcc python2-devel python-pip upx;
  echo -ne \"------\nEND DEPENDENCIES INSTALL\n\";"
docker exec -ti $DOCKER_CONTAINER_ID /bin/bash -xec "pip install -r requirements.txt;
  echo -ne \"------\nEND PIP REQUIREMENTS INSTALL\n\";"
docker exec -ti $DOCKER_CONTAINER_ID /bin/bash -xec "pyinstaller --onefile --noconfirm --clean --log-level=WARN --strip --runtime-tmpdir /dev/shm akroma-mn-setup.py;
  echo -ne \"------\nEND akroma-mn-setup BUILD\n\";"
docker exec -ti $DOCKER_CONTAINER_ID /bin/bash -xec "pyinstaller --onefile --noconfirm --clean --log-level=WARN --strip --runtime-tmpdir /dev/shm akroma-mn-utils.py;
  echo -ne \"------\nEND akroma-mn-utils BUILD\n\";"
docker ps -a
docker stop $DOCKER_CONTAINER_ID
docker rm -v $DOCKER_CONTAINER_ID
