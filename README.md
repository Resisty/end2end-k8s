# End to End Kubernetes Cluster Check

This project facilitates a container which supports, for example:
* connecting to a (positional argument) k8s cluster
* creating a test service on that cluster
* waiting for the service to set up an ELB
* waiting for the address to be routable
* HTTP GETing the address
* deleting the test service on that cluster

## Notes
1. This project is tightly coupled to the Puppet project at my previous employer, where various critical secrets are stored in hiera-gpg. The rundeck module dictates how those secrets are laid down on the rundeck server(s), e.g. their paths and filenames. As of the time of this writing, if you are unsure where your secrets are, you should check `$CODE_HOME/puppet/modules/rundeck/managed_secrets.pp` and `$CODE_HOME/puppet/hiera/gpg/roles/rundeck-server.gpg`.
1. These secrets are expected to be exported via [environment variables](#environment-variables). Depending on the subcommand(s) you wish to run, you should make sure you are setting the required variables correctly or be willing to pass the values in as argument [options](#options). Be sure to check the [examples](#example-check).

## <a name="defaults">Defaults</a>
There are a fair number of default values which may need to be overridden or updated as the project changes.
Check `./library/defaults.py`

Additionally, kubectl is invoked in a subshell and relies on `./.kube/config`. Clusters are mapped 1:1 to clusters and program invocation relies on those names.

## Development
To set up the project for development, execute `bash developer.sh && source bin/activate`

### Tests
When developing, you should:
* add unit tests to librarytests/
* update librarytests/__init__.py's `__all__` variable with your new tests
* evaluate your changes by running `python3 tests.py` or `bash self_check.sh`

## Example Operation
<a name="example-check">Example Check Syntax</a>
```
docker run -e DD_API_KEY=$(cat dd_secrets.txt) \
-e LEMUR_USER=$(cat lemur_secrets.txt | head -1) \
-e LEMUR_PASS=$(cat lemur_secrets.txt | tail -1) \
docker.examplecom/end2end-k8s \
check ${cluster_name} \
[options]
```
<a name="example-refresh">Example Refresh Syntax</a>
```
docker run -e SECRETS_MAP=$(cat secrets_map.yaml) \
-e LEMUR_USER=$(cat lemur_secrets.txt | head -1) \
-e LEMUR_PASS=$(cat lemur_secrets.txt | tail -1) \
docker.example.com/end2end-k8s \
refresh mako-k8s-secret-1
[options]
```

## <a name="commands">Commands</a>
1. <a name="command-check">`check`</a>
    * Runs the end-to-end check on the positional cluster.
1. <a name="command-clusters">`clusters`</a>
    * Examines the kubectl config and enumerates clusters.
1. <a name="refresh-secrets">`refresh`</a>
    * Refreshes the secret(s) on a kubernetes cluster. Secrets are tied to ${a service which manages kubernetes services} and/or users.
    * Takes a named k8s secret as [positional argument](#arguments) and relies on a [secrets map](#refresh-secretsmap).
    * As a result of the handling of this secret map, this command is specifically designed with a [Puppet](#puppet)+Rundeck workflow in mind.

## <a name="options">Options</a>
1. Default values for project contained in `./library/defaults.py`
    * `-v`, `--verbose`, `-vvv`
        Verbosity level for logging statements. Counts from 0, the minimum and [default](#defaults), to three, the maximum.
    * `-k`, `--kubeconfig`
        Location of kubectl config file. [Defaults](#defaults) to `/.kube/config`.
1. Options for [`check`](#command-check)
    * `-d`, `--datadog_secrets`
        Datadog api key. If you do not wish to pass this in on the command line, you should use the [environment variable](#environment-variables).
1. Options for [`clusters`](#command-clusters)
    * `-j`, `--json`
        Whether or not to print clusters as JSON (additionally, JSON formatted for the Rundeck values provider).
1. Options for [`refresh`](#refresh-secrets)
    * <a name="refresh-secretsmap">`-s`, `--secretsmap`</a>
        Multiline string of YAML mapping secret(s) to their configurations. _THIS IS VERY SPECIFIC AND YOU SHOULD CHECK THE [EXAMPLE](https://replace_this_with_an_actual_url/end2end_k8s/secrets_map.yaml.example)_
    * The production map is stored in hiera-gpg in [Puppet](#puppet) and will be created on the rundeck server(s) as `/var/lib/rundeck/var/storage/content/secrets/rundeck-mako-secrets-map.yaml`

## <a name="arguments">Positional Arguments</a>
1. Arguments for [`check`](#command-check)
    * `cluster` The name of the cluster to create a service on, check it, and delete it.
1. Arguments for [`refresh`](#refresh-secrets)
    * `secret` The name of the secret to refresh across clusters+namespaces (mapped in the [secretsmap](#refresh-secretsmap))

## <a name="environment-variables">Environment Variables</a>
1. Variables for project regardless of subcommand
    * `LEMUR_USER` Name of the lemur user with which to generate K8s client
      certificates. Required.
    * `LEMUR_PASS` Password for the lemur user with which to generate K8s
      client cerficates. Required.
1. Variables for [`check`](#command-check)
    * `DD_API_KEY` value of the Datadog API key. Allows submission of information to DD's ingress address for your account.
1. Variables for [`refresh`](#command-refresh)
    * `SECRETS_MAP` a multiline string describing secrets tied to MAKO and their configuration(s). Might contain multiple instances across K8s clusters and may represent IAM keys or S3 bucket files. Make sure to view the [example](https://replace_this_with_an_actual_url/end2end_k8s/secrets_map.yaml.example)
