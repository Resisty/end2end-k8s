#!/bin/bash

set -xe

declare -r current_dir=$(cd "$(dirname "$0")"; pwd)
declare -r image_name="end2end-k8s"

PREFIX=docker.example.com/${image_name}
TAG="v1"

build_image() {
  docker build -t ${PREFIX}:${TAG} ${current_dir}
}

self_check() {
  docker run --entrypoint=/bin/sh ${PREFIX}:${TAG} self_check.sh
}

cleanup() {
  rm -rf ${current_dir}/*
  docker ps -a | grep "${PREFIX}:${TAG}" | awk '{print $1}' | xargs docker rm
  images=$(docker images | grep "${PREFIX}:${TAG}" | awk '{print $1 ":" $2}')
  if [ -n "${images}" ]
  then
	  echo "${images}" | xargs -n 1 docker rmi
  fi
}

build_image
self_check
cleanup

exit 0

