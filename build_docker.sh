#!/bin/bash

set -xe

declare -r current_dir=$(cd "$(dirname "$0")"; pwd)
declare -r image_name="end2end-k8s"

PREFIX=docker.example.com/${image_name}
TAG="v1"

build_image() {
  docker build -t ${PREFIX}:${TAG} ${current_dir}
}

push_to_registry() {
  docker push ${PREFIX}:${TAG}
}

cleanup() {
  rm -rf ${current_dir}/*
}

build_image
push_to_registry
cleanup

exit 0

