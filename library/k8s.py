#!/usr/bin/env python
''' Python wrapper for kubectl
'''

import subprocess
import shlex
import tempfile
import os
import logging
import re
import time
import functools
from library import defaults
from library import lemur
import requests

LOGGER = logging.getLogger(defaults.LOGGER)
WAIT = 10
TIMEOUT = 180

def lemur_setup(func):
    ''' Create a decorator to ensure we have client certificates from Lemur
    '''
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        ''' The wrapper will create certificates if the client is not yet setup
        '''
        if not self.setup:
            LOGGER.info('Lemur certificates not set up. Generating for \
cluster "%s"',
                        self.cluster)
            certset = lemur.CertificateSet(self.cluster, self.kubeconfig)
            certset.run()
            self.setup = True
        # func will be callable unless somebody misuses it and that's on them
        # pylint: disable=not-callable
        return func(self, *args, **kwargs)
    return wrapper

class KubeError(Exception):
    ''' Custom kube error
    '''
    def __init__(self, *args, **kwargs):
        ''' Initialization method
        '''
        Exception.__init__(self, *args, **kwargs)
class KubeSvcNotFoundError(KubeError):
    ''' Custom kube error for service not found
    '''
    pass
class KubeProcError(KubeError):
    ''' Custom kube error for subprocess errors
    '''
    pass
class KubeIngressNotFoundError(KubeError):
    ''' Custom kube error for subprocess errors
    '''
    pass
class KubeRequestError(KubeError):
    ''' Custom kube error for requests errors
    '''
    pass

class JustOKKube(object):
    ''' Wrap kubectl with an object/methods
    '''
    def __init__(self, cluster, kubeconfig=defaults.KUBECONFIG):
        ''' Initialization method
            Positional Arguments:
                cluster: Dictionary for cluster containing certificats and
                         master address
        '''
        self._cluster = cluster
        self._servicefile = None
        self._deploymentfile = None
        self._ingress = None
        self._kubeconfig = kubeconfig
        self._setup = None
    @property
    def setup(self):
        ''' Return whether or not we have been set up
        '''
        return self._setup
    @setup.setter
    def setup(self, is_setup):
        ''' Store whether or not we have been set up
        '''
        self._setup = is_setup
    @property
    def cluster(self):
        ''' Return the cluster
        '''
        return self._cluster
    @property
    def kubeconfig(self):
        ''' Return the kubeconfig
        '''
        return self._kubeconfig
    @staticmethod
    def find_ingress(text):
        ''' Function to look for an ELB-backed service's address
        '''
        LOGGER.info('Looking for ingress in text: "%s"', text)
        regex = r'''Ingress:\s+([\w\.-]+)\n'''
        result = re.search(regex, text)
        try:
            # result.groups() is definitely callable
            # pylint: disable=not-callable
            return result.groups()[0]
        except (AttributeError, IndexError):
            message = ('Unable to find LoadBalancer Ingress address in text: \
                       "%s"' % text)
            raise KubeIngressNotFoundError(message)
    @staticmethod
    def kubefile(content):
        ''' Generic way to generate a k8s yaml file from content
            Positional Arguments:
                content: raw string to put in file
        '''
        _, path = tempfile.mkstemp()
        with open(path, 'w') as handle:
            # handle.write() is definitely callable
            # pylint: disable=not-callable
            handle.write(content)
            return path
    @property
    def servicefile(self):
        ''' Generate and keep track of a k8s service yaml file
        '''
        if not self._servicefile:
            LOGGER.info('Service file does not exist, creating.')
            self._servicefile = self.kubefile(defaults.SERVICE_YAML['content'])
        return self._servicefile
    @property
    def deploymentfile(self):
        ''' Generate and keep track of a k8s deployment yaml file
        '''
        if not self._deploymentfile:
            LOGGER.info('Deployment file does not exist, creating.')
            self._deploymentfile = self.kubefile(defaults
                                                 .DEPLOYMENT_YAML['content'])
        return self._deploymentfile
    @staticmethod
    def run_it(cmd):
        ''' Run a subprocess command
        '''
        LOGGER.info('Executing k8s command: "%s"', cmd)
        proc = subprocess.Popen(shlex.split(cmd),
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
        out, err = proc.communicate()
        if err:
            raise KubeProcError(err)
        return out
    def create_deploy(self):
        ''' Abstraction for subprocessing of kubectl create -f
        '''
        return self._adjust_cluster('create', self.deploymentfile)
    def create_svc(self):
        ''' Abstraction for subprocessing of kubectl create -f
        '''
        return self._adjust_cluster('create', self.servicefile)
    def desc_svc(self):
        ''' Abstraction for subprocessing of kubectl describe svc

        '''
        out = self._adjust_cluster('describe svc', defaults.SERVICE_YAML['name'])
        if bytearray('not found', 'utf-8') in out:
            raise KubeSvcNotFoundError('Service "%s" should be created but \
was not found with "kubectl get svc"')
        return out
    def create_file(self, kubefile):
        ''' Abstraction for subprocessing of kubectl create -f on an arbitrary
            file path
            Positional Arguments:
                kubefile: path to a kubernetes yaml file
        '''
        return self._adjust_cluster('create', kubefile)
    def delete_deploy(self):
        ''' Abstraction for subprocessing of kubectl delete -f
        '''
        return self._adjust_cluster('delete', self.deploymentfile)
    def delete_svc(self):
        ''' Abstraction for subprocessing of kubectl delete -f
        '''
        out = self._adjust_cluster('delete', self.servicefile)
        self._ingress = None
        return out
    @lemur_setup
    def run_raw(self, command):
        ''' Issue a raw command to kubectl. Command will be prepended with
            "kubectl --context %s" % cluster
        '''
        cmd = defaults.KUBECTL % (self._kubeconfig, self._cluster, command)
        return self.run_it(cmd)
    @lemur_setup
    def _adjust_cluster(self, which, substr):
        cmd = defaults.KUBECTL % (self._kubeconfig,
                                  self._cluster,
                                  defaults.SUB_KUBECTL[which] % substr)
        return self.run_it(cmd)
    def cleanup(self):
        ''' Remove service file
        '''
        LOGGER.info('Removing service file "%s"...', self.servicefile)
        os.remove(self.servicefile)
        LOGGER.info('Removed service file "%s"', self.servicefile)

    def ingress_address(self, timeout=TIMEOUT):
        ''' Check the service (if it exists) for a LoadBalancer Ingress and
            return it or time out
        '''
        out = self.desc_svc()
        t_slept = 0
        while True:
            if t_slept >= timeout:
                raise KubeIngressNotFoundError('LoadBalancer did not come up \
in timeout of %s. Stop.', timeout)
            try:
                self._ingress = 'http://' + (self
                                             .find_ingress(out
                                                           .decode('utf-8')))
                break
            except KubeIngressNotFoundError:
                LOGGER.info('LoadBalancer Ingress not available. Waiting \
%ss...', WAIT)
                t_slept += WAIT
                time.sleep(WAIT)
                out = self.desc_svc()
    def verify_ingress(self, timeout=TIMEOUT):
        ''' Make a request (HTTP GET) against the LoadBalancer Ingress and
            return it or time out
        '''
        if not self._ingress:
            self.ingress_address()
        t_slept = 0
        while True:
            if t_slept >= timeout:
                raise KubeRequestError('Unable to successfully query the \
LoadBalancer Ingress before timing out.')
            try:
                result = requests.get(self._ingress)
                if result.status_code != 200:
                    raise KubeRequestError('Service is reachable but returned \
%s with text "%s"', result.status_code, result.text)
                return 'Service ingress returned 200'
            except requests.exceptions.ConnectionError:
                LOGGER.info('Address not yet reachable. Waiting %s...', WAIT)
                t_slept += WAIT
                time.sleep(WAIT)
