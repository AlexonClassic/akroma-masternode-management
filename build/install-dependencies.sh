#!/bin/sh -xe

# Install Dependencies within docker containers and for the building of the binaries

docker run --privileged -d -ti -e "container=docker"  -v /sys/fs/cgroup:/sys/fs/cgroup -v `pwd`:/akroma-masternode-management:rw  centos:centos${OS_VERSION}   /usr/sbin/init
DOCKER_CONTAINER_ID=$(docker ps | grep centos | awk '{print $1}')
docker logs $DOCKER_CONTAINER_ID
docker exec -ti $DOCKER_CONTAINER_ID /bin/bash -xec "yum update -y && yum --enablerepo=extras install epel-release -y && yum --enablerepo=extras install gcc python2-devel python-pip python-setuptools upx -y && echo -ne \"------\nEND DEPENDENCIES INSTALL\n\";"
docker exec -ti $DOCKER_CONTAINER_ID /bin/bash -xec "find / -name requirements.txt ; pip install -r /akroma-masternode-management/source/requirements.txt &&
  echo -ne \"------\nEND PIP REQUIREMENTS INSTALL\n\";"
