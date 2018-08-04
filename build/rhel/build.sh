#!/bin/sh -xe

# This script starts docker and systemd on el7

echo "Line 5"
docker run --privileged -d -ti -e "container=docker"  -v /sys/fs/cgroup:/sys/fs/cgroup -v `pwd`:/akroma-masternode-managememt:rw  centos:centos${OS_VERSION}   /usr/sbin/init
DOCKER_CONTAINER_ID=$(docker ps | grep centos | awk '{print $1}')
docker logs $DOCKER_CONTAINER_ID
echo "Line 9"
docker exec -ti $DOCKER_CONTAINER_ID /bin/bash -xec "yum --enablerepo=extras install epel-release -y 
  && yum --enablerepo=extras install gcc python2-devel python-pip upx -y 
  && echo -ne \"------\nEND DEPENDENCIES INSTALL\n\";"
echo "Line 12"
docker exec -ti $DOCKER_CONTAINER_ID /bin/bash -xec "find / -name *pip* ; /usr/bin/pip install -r /akroma-masternode-management/source/requirements.txt &&
  echo -ne \"------\nEND PIP REQUIREMENTS INSTALL\n\";"
echo "Line 15"
docker exec -ti $DOCKER_CONTAINER_ID /bin/bash -xec "pyinstaller --onefile --noconfirm --clean --log-level=WARN --strip --runtime-tmpdir /dev/shm akroma-mn-setup.py &&
  echo -ne \"------\nEND akroma-mn-setup BUILD\n\";"
echo "Line 18"
docker exec -ti $DOCKER_CONTAINER_ID /bin/bash -xec "pyinstaller --onefile --noconfirm --clean --log-level=WARN --strip --runtime-tmpdir /dev/shm akroma-mn-utils.py &&
  echo -ne \"------\nEND akroma-mn-utils BUILD\n\";"
echo "Line 21"
docker ps -a
docker stop $DOCKER_CONTAINER_ID
docker rm -v $DOCKER_CONTAINER_ID
