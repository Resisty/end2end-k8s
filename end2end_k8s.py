#!/usr/bin/env python
''' Main script of k8s end to end cluster check
'''
import argparse
import logging
import json
import os
import sys
from library import defaults, k8s, dd, kube_choices, secret
import yaml

LOGGER = logging.getLogger(defaults.LOGGER)

def run_tests(args):
    ''' Defaults function for argument parser
        Run the end to end test
    '''
    kube = k8s.JustOKKube(args.clustername, args.kubeconfig)
    LOGGER.info('Attempting to create, check, and delete service on cluster \
"%s"', args.clustername)
    try:
        kube.create_deploy()
        kube.create_svc()
        event_msg = kube.verify_ingress()
        alert_type = 'info'
    except (k8s.KubeError, ValueError) as error:
        event_msg = str(error)
        alert_type = 'error'
        LOGGER.exception(event_msg)
    finally:
        kube.delete_deploy()
        kube.delete_svc()
    kube.cleanup()
    LOGGER.info('Attempting to send event message "%s" to datadog for cluster "%s"',
                event_msg,
                args.clustername)
    dd_client = dd.DDClient(args.dd_api_key)
    result = dd_client.send_event(event_msg,
                                  alert_type=alert_type,
                                  tags=['k8s_cluster:%s' % args.clustername])
    LOGGER.info('Results from sending event to datadog: "%s"', result.text)

def list_choices(args):
    ''' List out the known clusters in the kubectl config file, if it exists
    '''
    if args.json:
        print(json.dumps([{'name': i, 'value': i}
                          for i in (kube_choices
                                    .KubeChoice
                                    .from_path(args.kubeconfig))]))
    else:
        print('\n'.join(kube_choices.KubeChoice.from_path(args.kubeconfig)))

def refresh_secrets(args):
    ''' This is a highly-specific workflow relying on a highly-specific
        configuration file. Use only if you know exactly what you're doing.
    '''
    secrets_map = yaml.load(args.secretsmap)
    try:
        secret_type = (secret
                       .SecretChoice
                       .from_str(secrets_map['secrets'][args.secret]['type']))
    except KeyError:
        LOGGER.exception('Unable to find secret "%s" in secrets map!',
                         args.secret)
        sys.exit(1)
    instances = [i for i in secrets_map['secrets'][args.secret]['instances']
                 if i['env'] == args.environment]
    the_secret = secret_type(args.secret,
                             instances,
                             secrets_map['aws_keys'],
                             args.kubeconfig)
    the_secret.create()

def mk_dd_api(argument):
    ''' Function to help argparse collect the value of the DD api key
        regardless of the way in which it was provided
    '''
    argument = argument or os.getenv('DD_API_KEY')
    if not argument:
        LOGGER.exception('Unable to find value for datadog API key from \
program args or environment variables. Will not be able to submit results to \
datadog.')
    return argument

def mk_secrets_map(argument):
    ''' Function to help argparse collect the value of the secret map
        regardless of the way in which it was provided
    '''
    argument = argument or os.getenv('SECRETS_MAP')
    if not argument:
        LOGGER.exception('Unable to find value for secrets map from \
program args or environment variables. Will not be able to refresh any \
secrets.')
    return argument

def main():
    ''' Main method
    '''
    parser = argparse.ArgumentParser('Test k8s clusters')
    parser.add_argument("-v", '--verbose',
                        help="Verbose",
                        action='count',
                        default=0)
    parser.add_argument('-k', '--kubeconfig',
                        help='Path to Kubectl Config file',
                        default=defaults.KUBECONFIG)
    subparsers = parser.add_subparsers(dest='subparser_name')
    check_parser = subparsers.add_parser('check')
    check_parser.add_argument('clustername',
                              help='Name of the cluster')
    check_parser.add_argument('-d', '--dd_api_key',
                              help='Datadog API key for submitting events.',
                              default='', # set default to ensure call to
                                          # mk_dd_api()
                              type=mk_dd_api)
    check_parser.set_defaults(func=run_tests)
    list_parser = subparsers.add_parser('clusters')
    list_parser.add_argument('-j', '--json',
                             help='Print clusters in json',
                             action='store_true',
                             default=False)
    list_parser.set_defaults(func=list_choices)
    refresh_parser = subparsers.add_parser('refresh')
    refresh_parser.add_argument('secret',
                                help='Name of the secret to refresh')
    refresh_parser.add_argument('-s', '--secretsmap',
                                help='Yaml string containing map of secrets \
to refresh',
                                default='',
                                type=mk_secrets_map)
    refresh_parser.add_argument('-e', '--environment',
                                help='Which environment to use for refreshing \
secrets. Environments are mutually exclusive but secrets exist in multiple \
environments.',
                                choices=['pipeline', 'prod'],
                                default='pipeline')
    refresh_parser.set_defaults(func=refresh_secrets)
    args = parser.parse_args()
    levels = [logging.WARN, logging.INFO, logging.DEBUG]
    level = levels[min(len(levels)-1, args.verbose)]
    LOGGER.setLevel(level)
    LOGGER.addHandler(logging.StreamHandler())
    args.func(args)

if __name__ == '__main__':
    main()
