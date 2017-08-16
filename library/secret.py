#!/usr/bin/env python
''' Module for abstraction(s) of shared secrets in AWS and Kubernetes.
'''
import logging
import abc
import base64
import os
from library import defaults, k8s
import boto3
import botocore

LOGGER = logging.getLogger(defaults.LOGGER)
K8S_SECRET = '''apiVersion: v1
kind: Secret
metadata:
  name: {name}
  namespace: {namespace}
type: Opaque
data:
  {key}: {content}'''

SECRETS_BYTES = 256

def secret_bytes():
    ''' Generate a string from random bytes.
    '''
    # What the hell this is: http://stackoverflow.com/a/16310739
    # Character sets:
    #             [-]               [A-Z]      [_]               [a-z]
    ord_letters = [45] + list(range(65, 91)) + [95] + list(range(97, 123))
    nbytes = SECRETS_BYTES
    nletters = len(ord_letters)
    naligned = nbytes - (nbytes % nletters)
    tbl = bytes.maketrans(bytearray(range(naligned)),
                          bytearray([ord_letters[b % nletters]
                                     for b in range(naligned)]))
    bytes2delete = bytearray(range(naligned, nbytes))
    return os.urandom(nbytes).translate(tbl, bytes2delete)

# pylint: disable=too-few-public-methods
class SecretChoice(object):
    ''' This class has a single class method and is intended to provide a way
        for a secrets map (dict) to choose the right kind of secret for its data
    '''
    @classmethod
    def from_str(cls, choice):
        ''' Return the type of secret based on choice
        '''
        return {'S3_K8s': MakoLemurSecret,
                'IAM_K8s': MakoIAMSecret}[choice]

class SharedSecret(object):
    ''' Abstract base class for a shared secret. Should not be implemented
        directly.
    '''
    __metaclass__ = abc.ABCMeta
    def __init__(self,
                 name,
                 secret_maps,
                 aws_keys,
                 kubeconfig=defaults.KUBECONFIG):
        ''' Initialization method.
            Positional arguments:
                name: Name of the secret.
                secret_maps: A list of maps containing the information
                    required to create or refresh a secret: s3 bucket name, key,
                    IAM keys to access the S3 bucket, k8s cluster
                aws_keys: A dict of names:access/secret keys; val in values()
                    should be able to be passed as **val to a boto3 client.
            Keyword arguments:
                kubeconfig: Path to kubernetes config file.
        '''
        self._name = name
        self._instances = secret_maps
        self._keys = aws_keys
        self._kubeconfig = kubeconfig
    @abc.abstractmethod
    def create(self):
        ''' Abstract method not implemented here, but must be implemented by
            subclasses. Secrets should be create()able.
        '''
        pass
    def update_k8s(self, instance, content):
        ''' Update the kubernetes cluster with the secret's content.
            Overridable, but generic enough (if the secrets map is correct)
            that it should be unnecessary.
            Positional Arguments:
                instance:
                    Dictionary configuration for a copy of a secret, e.g. on a
                    given K8s cluster
                content:
                    Bytes of raw content to be encapsulated in a K8s secret, e.g.
                    plaintext AWS secret/access keys in INI format
        '''
        content = base64.urlsafe_b64encode(content)
        kube = k8s.JustOKKube(instance['cluster'], self._kubeconfig)
        kwargs = {'name': self._name,
                  'namespace': instance['namespace'],
                  'key': instance['key'],
                  'content': content.decode('ascii')}
        k8s_secret = K8S_SECRET.format(**kwargs)
        secretfile = kube.kubefile(k8s_secret)
        delete = ('delete secret %s --namespace %s'
                  % (self._name, instance['namespace']))
        try:
            LOGGER.info('Trying to delete secret "%s" on cluster "%s", \
namespace "%s"',
                        self._name,
                        instance['cluster'],
                        instance['namespace'])
            kube.run_raw(delete)
        except k8s.KubeProcError as err:
            if 'NotFound' not in str(err):
                raise
        LOGGER.info('Trying to recreate secret "%s" on cluster "%s", \
namespace "%s"',
                    self._name,
                    instance['cluster'],
                    instance['namespace'])
        kube.create_file(secretfile)
class MakoLemurSecret(SharedSecret):
    ''' This secret is comprised of a base64-encoded, 256 byte string stored in
        an S3 bucket and a K8s secret, provided at instantiation by a map
    '''
    S3_OBJECT = {'ACL': 'private',
                 'Body': None,
                 'Bucket': None,
                 'Key': None,
                 'ServerSideEncryption': 'AES256'}

    def create(self):
        ''' Must-be-overridden method:
            Create the S3 and K8s secret(s) from map
        '''
        LOGGER.info('Refreshing instances for secret "%s"', self._name)
        for instance in self._instances:
            botocreds = self._keys[instance['aws_keys']]
            content = secret_bytes()
            self._put_s3(botocreds, instance, content)
            self.update_k8s(instance, content)
    @staticmethod
    def _put_s3(creds, instance, content):
        ''' Send the secret's content to the S3 bucket.
        '''
        client = boto3.client('s3', **creds)
        kwargs = MakoLemurSecret.S3_OBJECT
        kwargs['Body'] = content
        kwargs['Bucket'] = instance['bucket']
        kwargs['Key'] = instance['key']
        response = client.put_object(**kwargs)
        LOGGER.info('HTTP result of putting S3 object: %s',
                    response['ResponseMetadata']['HTTPStatusCode'])
class MakoIAMSecret(SharedSecret):
    ''' This secret is comprised of AWS IAM secret/access keys stored in
        multiple k8s secrets.
    '''
    def create(self):
        ''' Create the secret according to its configuration from the secrets
            map
        '''
        LOGGER.info('Refreshing instances for secret "%s"', self._name)
        refreshed_users = []
        for instance in self._instances:
            # A given iam_user is managed by a set of aws_keys (which signify
            # an account). If an iam_user has been updated by a set of
            # aws_keys, do not update it again. However, if the same name
            # exists in a different account (a different aws_keys), update the
            # iam_user.
            if {instance['aws_keys']: instance['iam_user']} not in refreshed_users:
                LOGGER.info('IAM user %s has not been refreshed for secret \
%s.  Refreshing.', instance['iam_user'], self._name)
                botocreds = self._keys[instance['aws_keys']]
                new_secret = self._update_keys(botocreds, instance['iam_user'])
                refreshed_users.append({instance['aws_keys']: instance['iam_user']})
            self.update_k8s(instance, new_secret)
    @staticmethod
    def _update_keys(creds, username):
        ''' Regenerate IAM secret/access keys and call update_k8s() on the
            result. If the user is at their quota for keys, delete the oldest
            key.
            Positional Arguments:
                creds: Dictionary of IAM credentials (secret/access key values)
                    for editing IAM keys
                username:
                    Name of IAM user for whom to refresh secrets
        '''
        iam = boto3.client('iam', **creds)
        try:
            newkey = iam.create_access_key(UserName=username)['AccessKey']
        # botocore.errorfactory.LimitExceededException does exist
        # pylint: disable=no-member
        except botocore.exceptions.ClientError as err:
            if 'LimitExceeded' not in str(err):
                raise
            previouskeys = iam.list_access_keys(UserName=username)
            oldest = min(previouskeys['AccessKeyMetadata'],
                         key=lambda x: x['CreateDate'])
            iam.delete_access_key(AccessKeyId=oldest['AccessKeyId'],
                                  UserName=username)
            newkey = iam.create_access_key(UserName=username)['AccessKey']
        creds = (defaults
                 .KEYREFRESH_CREDS_FMT
                 % (newkey['AccessKeyId'], newkey['SecretAccessKey']))
        # update_k8s() requires content be bytes
        return bytes(creds, 'ascii')
