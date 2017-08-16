#!/usr/bin/env python
"""Tests KubeChoice objects and settings

Example:
    import unittest
    suite = test_config.suite()
    unittest.TextTestRunner().run(suite)

"""
import unittest
import os
from library import kube_choices
import yaml

TMP_CONF = 'kubectl_conf'

class KubeChoiceTestCase(unittest.TestCase):
    ''' Test cases for library.kube_choices
    '''
    def test_constructor(self):
        ''' Test the constructor without an argument
        '''
        self.assertTrue(isinstance(kube_choices.KubeChoice(),
                                   kube_choices.KubeChoice))

    def test_constructor_with_arg(self):
        ''' Test the constructor to create a Config object with an argument
        '''
        self.assertTrue(isinstance(kube_choices.KubeChoice('kube/config'),
                                   kube_choices.KubeChoice))

    def test_constructor_with_bad_arg(self):
        ''' Test the constructor to succeed with a bad argument, and handle
            errors when unable to retrieve choices
        '''
        kubechoice = kube_choices.KubeChoice('not_a_file')
        self.assertEqual(kubechoice.choices, [])

    def setUp(self):
        ''' Create a kube_choices.KubeChoice object for testing with a temporary file
        '''
        self.config_yaml = {'contexts': [{'name': 'test_cluster1'},
                                         {'name': 'test_cluster2'}]}
        with open(TMP_CONF, 'w') as kube_yaml:
            kube_yaml.write(yaml.dump(self.config_yaml))
        self.conf = kube_choices.KubeChoice(TMP_CONF)

    def tearDown(self):
        ''' Clean up after ourselves, remove temporary config file
        '''
        os.remove(TMP_CONF)
    def test_config(self):
        ''' Test the config property
        '''
        self.assertEqual(self.conf.config,
                         TMP_CONF)
    def test_config_setter(self):
        ''' Test the config setter property
        '''
        old_conf = self.conf.config
        self.conf.config = 'new_yaml'
        self.assertNotEqual(self.conf.config, old_conf)

def suite():
    ''' Create a suite of tests
    '''
    the_suite = unittest.TestLoader().loadTestsFromTestCase(KubeChoiceTestCase)
    return the_suite
