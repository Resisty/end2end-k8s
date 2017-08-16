#!/usr/bin/env python
''' Wrap Datadog's API, at least for events
'''

import logging
import json
from library import defaults
import requests

LOGGER = logging.getLogger(defaults.LOGGER)

class DDClientError(Exception):
    ''' Custom error
    '''
    def __init__(self, *args, **kwargs):
        ''' Initialization method
        '''
        Exception.__init__(self, *args, **kwargs)
class ApiKeyNotFoundError(DDClientError):
    ''' Custom error
    '''
    pass
class DatadogRequestError(DDClientError):
    ''' Custom error
    '''
    pass

class DDClient(object):
    ''' Not-too-bad wrapper around datadog API
    '''
    def __init__(self, apikey):
        ''' Initialization method
            Positional Arguments:
                apikey: Secret string allowing submission to Datadog for your
                        account
        '''
        self._apikey = apikey
        self._run = False
        self._url = 'https://app.datadoghq.com/api/v1/events'
        self._headers = {'Content-type': 'application/json'}
    @property
    def apikey(self):
        ''' Get the api key from shell exports file and/or return it
        '''
        return self._apikey
    def send_event(self,
                   text,
                   title='K8s End-to-End Test',
                   tags=None,
                   alert_type='info'):
        ''' Send an event via Datadog API
            ...shittily
        '''
        data = {'title': title,
                'text': text,
                'priority': 'normal',
                'tags': ['end2end_k8s'],
                'alert_type': alert_type}
        if tags:
            data['tags'] += tags
        params = {'api_key': self.apikey}
        result = requests.post(self._url,
                               params=params,
                               headers=self._headers,
                               data=json.dumps(data))
        LOGGER.info('Made a request to "%s"', self._url)
        LOGGER.info('Request headers: "%s"', self._headers)
        LOGGER.info('Request json: "%s"', json.dumps(data))
        if result.status_code not in range(200, 400):
            msg = ('Status code: %s\nText: %s\n'
                   % (result.status_code, result.text))
            raise DatadogRequestError(msg)
        return result
