#!/bin/sh -xe

# Install Dependencies within docker containers and for the building of the binaries

DOCKER_CONTAINER_ID=$(docker ps | grep centos | awk '{print $1}')
docker logs $DOCKER_CONTAINER_ID
docker exec -ti $DOCKER_CONTAINER_ID /bin/bash -xec "yum --enablerepo=extras install epel-release -y && yum --enablerepo=extras install gcc python2-devel python-pip upx -y && echo -ne \"------\nEND DEPENDENCIES INSTALL\n\";"
docker exec -ti $DOCKER_CONTAINER_ID /bin/bash -xec "find / -name requirements.txt ; pip install -r /akroma-masternode-management/source/requirements.txt &&
  echo -ne \"------\nEND PIP REQUIREMENTS INSTALL\n\";"
