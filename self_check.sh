#!/bin/sh
pip3 install pylint
pylint end2end_k8s.py
pylint library/
python3 tests.py
