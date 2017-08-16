#!/usr/bin/env python
''' Set up defaults for project
'''
import os

LOGGER = 'end2end_k8s'
DEFAULT_SECRETS = '/etc/kube/ssl'
DEFAULT_DD_SECRETS = DEFAULT_SECRETS + '/datadog_api'
KUBE_SECRETS_DIR = '/etc/kube/ssl/'
KUBECONFIG = (os.path.abspath(os.path.join(os.path.dirname(__file__),
                                           '..',
                                           '.kube/config')))
KUBECTL = '''kubectl --kubeconfig %s --context %s %s'''

SUB_KUBECTL = {'create': 'create -f %s',
               'delete': 'delete -f %s',
               'describe svc': 'describe svc %s'}

SERVICE_YAML = {'content': '''apiVersion: v1
kind: Service
metadata:
  name: end2end-externalelbtest
  labels:
    name: end2end-externalelbtest
spec:
  type: LoadBalancer
  ports:
    # the port that this service should serve on
  - port: 80
  selector:
    name: end2end-externalelbtest''',
                'name': 'end2end-externalelbtest'}
DEPLOYMENT_YAML = {'content': '''apiVersion: extensions/v1beta1
kind: Deployment
metadata:
  name: end2end-externalelbtest
  labels:
    name: end2end-externalelbtest
spec:
  replicas: 2
  template:
    metadata:
      labels:
        name: end2end-externalelbtest
    spec:
      containers:
      - name: nginx
        image: nginx:1.9.1
        ports:
        - containerPort: 80''',
                   'name': 'end2end-externalelbtest'}
KEYREFRESH_CONFIG = '/mako-secrets-map.yaml'
KEYREFRESH_CREDS_FMT = '''[default]
aws_access_key_id = %s
aws_secret_access_key = %s
'''
KEYREFRESH_SECRET_FMT = '''apiVersion: v1
kind: Secret
metadata:
  name: %s
  namespace: %s
type: Opaque
data:
  credentials: %s'''
