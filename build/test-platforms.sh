#!/bin/sh -xe

# This script will be used to test various OS types and can be extended to offer more testing to more platforms as time goes on.

DOCKER_CONTAINER_ID=$(docker ps | grep centos | awk '{print $1}')
docker exec -ti $DOCKER_CONTAINER_ID /bin/bash -xec "cd /akroma-masternode-management/source && ls -lah dist/akroma-mn-setup && ./dist/akroma-mn-setup -h && yes | ./akroma-mn-setup && akroma-mn-utils
  echo -ne \"------\nEND akroma-mn-setup AND akroma-mn-utils CENTOS 7 TEST\n\";"
