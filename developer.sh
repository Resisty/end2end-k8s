#!/usr/bin/env bash
cd $(dirname $0)
virtualenv . --python=$(which python3) && \
source bin/activate && \
pip3 install -r requirements-dev.txt
