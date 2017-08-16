#!/usr/bin/env python
''' This module provides a way to obtain k8s client certificates from the Lemur
    API
'''

import os
import datetime
import collections
import functools
import hashlib
import logging
from library import defaults
import yaml
import requests

LOGGER = logging.getLogger(defaults.LOGGER)
LEMUR_URL = collections.defaultdict(lambda: 'https://lemur.example.com')
LEMUR_URL['prod'] = 'https://lemur-prod.example.com'
AUTHORITIES = collections.defaultdict(lambda: {'name': 'PipelineCA'})
AUTHORITIES['prod'] = {'name': 'ProdCA'}
MANIFEST = {'description': "Client Certificate for Rundeck Automation",
            'authority': '',
            'commonName': 'Rundeck',
            'validityStart': '',
            'validityEnd': '',
            'country': 'US',
            'state': 'OR',
            'location': 'Portland',
            'organization': 'rbac-group',
            'organizationalUnit': 'rbac-group',
            'owner': 'rbac-group@example.com',
            'active': True,
            'extensions': {'keyUsage': {'isCritical': True,
                                        'useDigitalSignature': True},
                           'extendedKeyUsage': {'isCritical': True,
                                                'clientAuth': True},
                           'subjectKeyIdentifier': {'isCritical': False,
                                                    'includeSKI': True}}}


class CertificateSetError(Exception):
    ''' Custom certificate error
    '''
    def __init__(self, *args, **kwargs):
        ''' Initialization method
        '''
        Exception.__init__(self, *args, **kwargs)
class CertificateSetConfigNotFoundError(CertificateSetError):
    ''' Custom certificateset error for config not found
    '''
    pass
class CertificateSetConfigError(CertificateSetError):
    ''' Custom certificateset error for unreadable config
    '''
    pass
class CertificateSet(object):
    ''' Create and place files according to kubeconfig for given cluster
    '''
    def __init__(self, cluster, kubeconfig=defaults.KUBECONFIG):
        ''' Initialization method
            Positional arguments:
                cluster: Name of the k8s cluster for which we need client certs
        '''
        self._cluster = cluster
        self._kubeconfig = kubeconfig
        try:
            with open(self._kubeconfig, 'r') as data:
                # data.read() is definitely callable
                # pylint: disable=not-callable
                config = yaml.load(data.read())
            cluster_obj = [i
                           for i in config['clusters']
                           if i['name'] == self._cluster][0]
            self._ca_file = cluster_obj['cluster']['certificate-authority']
            context_obj = [i
                           for i in config['contexts']
                           if i['name'] == self._cluster][0]
            user = [i
                    for i in config['users']
                    if i['name'] == context_obj['context']['user']][0]
            self._user = user['name']
            self._cert_file = user['user']['client-certificate']
            self._key_file = user['user']['client-key']
        except IOError:
            raise CertificateSetConfigNotFoundError('Unable to open %s for \
configuration.', self._kubeconfig)
        except KeyError:
            raise CertificateSetConfigError('Malformed configuration in %s, \
unable to read certificate file paths.', self._kubeconfig)
    @property
    # pylint: disable=invalid-name
    def ca(self):
        ''' Return the location of the ca file
        '''
        return self._ca_file
    @property
    def cert(self):
        ''' Return the location of the certificate file
        '''
        return self._cert_file
    @property
    def key(self):
        ''' Return the location of the key file
        '''
        return self._key_file
    def run(self):
        ''' Get the certificates and write them to file
        '''
        # str.split() is definitely callable
        # pylint: disable=not-callable
        lemur_env = self._user.split('-')[0]
        certs = Lemur.get_from(lemur_env)
        # dict.items() is definitely callable
        # pylint: disable=not-an-iterable
        for key, content in certs.items():
            filepath = os.path.join(os.path.dirname(self._kubeconfig),
                                    self.__getattribute__(key))
            with open(filepath, 'w') as data:
                LOGGER.info('Writing certificate contents to file "%s"',
                            filepath)
                # data.write() is definitely callable
                # pylint: disable=not-callable
                data.write(content)

def auth(func):
    ''' Decorator to make sure we've authenticated before making API calls
    '''
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        ''' The wrapper ensures we have a token (we have authenticated) before
            calling func()
        '''
        if not self.token:
            self.authenticate()
        return func(self, *args, **kwargs)
    return wrapper

# Unfortunately, we need those items. Theoretically we could down it to 8 by
# combining url and api, but that's still more than 7.
# pylint: disable=too-many-instance-attributes
class Lemur(object):
    ''' Abstraction for a Lemur instance from which we can obtain certificates
    '''
    @classmethod
    def get_from(cls, environment):
        ''' Convenience method
        '''
        return cls(environment).get_or_create_cert()
    def __init__(self, environment='prod'):
        ''' Initialization method
        '''
        self._env = environment
        self._url = LEMUR_URL[environment]
        self._user = os.getenv('LEMUR_USER')
        self._pass = os.getenv('LEMUR_PASS')
        self._api = '/api/1'
        self._authuri = '/auth/login'
        self._certuri = '/certificates'
        self._token = None
        self._man = None
    @property
    def manifest(self):
        ''' Generate a manifest for requesting client certificates
        '''
        if not self._man:
            self._man = MANIFEST
            self._man['authority'] = AUTHORITIES[self._env]
            self._man['validityStart'] = datetime.datetime.now().strftime('%F')
            self._man['validityEnd'] = ((datetime.datetime.now() +
                                         datetime.timedelta(1))
                                        .strftime('%F'))
            digest = (hashlib
                      .sha256(yaml
                              .dump(self._man)
                              .encode('utf-8'))
                      .hexdigest())
            self._man['description'] = '%s:%s' % (digest,
                                                  self._man['description'])
        return self._man
    @property
    def token(self):
        ''' Return auth token. Decorator @auth shouldn't be accessing private
            attributes, so publicize it
        '''
        return self._token
    def authenticate(self):
        ''' Request an authentication token for API calls with user/pass
        '''
        data = {'username': self._user,
                'password': self._pass}
        response = requests.post(''.join([self._url,
                                          self._api,
                                          self._authuri]),
                                 json=data)
        self._token = response.json()['token']
    @property
    @auth
    def headers(self):
        ''' Generate auth header for API calls
        '''
        return {'Authorization': 'Bearer %s' % self.token,
                'Content-type': 'application/json'}
    @auth
    def get_or_create_cert(self):
        ''' Retrieve the cert for our manifest if it exists or create a new
        one.
        '''
        url = ''.join([self._url, self._api, self._certuri])
        headers = self.headers
        params = {'sortBy': 'date_created',
                  'sortDir': 'desc',
                  'filter': 'description;%s' % self.manifest['description']}
        response = requests.get(url,
                                headers=headers,
                                params=params)
        data = response.json()
        if data['total'] < 1:
            ca_cert, client_cert, cert_id = self.create_cert()
        else:
            item = data['items'][0]
            ca_cert = item['chain']
            client_cert = item['body']
            cert_id = item['id']
        key = self.cert_key(cert_id)
        return {'ca': ca_cert,
                'cert': client_cert,
                'key': key}
    @auth
    def create_cert(self):
        ''' Create a cert from our manifest
        '''
        url = ''.join([self._url, self._api, self._certuri])
        headers = self.headers
        response = requests.post(url,
                                 headers=headers,
                                 json=self.manifest)
        data = response.json()
        ca_cert = data['chain']
        client_cert = data['body']
        cert_id = data['id']
        return ca_cert, client_cert, cert_id
    @auth
    def cert_key(self, cert_id):
        ''' Obtain the key for a cert given an id
            Positional arguments:
                cert_id: The numerical id of the certificate for which to
                         obtain the key
        '''
        url = ''.join([self._url,
                       self._api,
                       self._certuri,
                       '/%s' % cert_id,
                       '/key'])
        headers = self.headers
        response = requests.get(url, headers=headers)
        return response.json()['key']
