#!/usr/bin/env python
''' Generate choices for kube contexts from kubectl config file
'''

import logging
from library import defaults
import yaml

LOGGER = logging.getLogger(defaults.LOGGER)

class KubeChoice(object):
    ''' Abstraction for handling kubectl config file
    '''
    @classmethod
    def from_path(cls, path):
        ''' Convenience method for use as choices keyword argument
            in argparse.ArgumentParser().add_argument()
        '''
        kubechoice = cls(path)
        return kubechoice.choices
    def __init__(self, configpath=defaults.KUBECONFIG):
        ''' Initialization method
        '''
        self._conf = configpath
        self._choices = []
        self._run = False
    @property
    def config(self):
        ''' Return the config path
        '''
        return self._conf
    @config.setter
    def config(self, conf):
        ''' Set the config path
        '''
        self._conf = conf
    @property
    def choices(self):
        ''' Get the choices from the config path (if they exist), save them,
            and return them. If they've been saved, just return them. Let users
            know if there was a problem.
        '''
        if not self._choices and not self._run:
            # extra check of self._run because maybe we don't get choices from
            # file
            try:
                with open(self._conf) as data:
                    kubedict = yaml.load(data.read())
                    self._choices = [i['name'] for i in kubedict['contexts']]
                    self._run = True
            except IOError:
                LOGGER.exception('Could not open kubectl config file "%s"',
                                 self._conf)
            except KeyError:
                LOGGER.exception('Malformed kubectl config file. Check \
contents of "%s"', self._conf)
            self._run = True
        return self._choices
