#!/usr/bin/env python

from ghapi.all import *
import os
import re
from kubernetes import client, config
import yaml
import base64

GITHUB_TOKEN = 'GITHUB_TOKEN'
GITHUB_REPOSITORY = 'GITHUB_REPOSITORY'

ENV_KUBECONFIG64 = 'WERF_KUBECONFIG_BASE64'
CM_NAME = 'release-channels-data'
CM_NAMESPACE = 'deckhouse-web-dev'

yamldata = ''

def write_output(var,value):
    with open(os.getenv('GITHUB_OUTPUT'), 'a') as output:
        output.write(f'{var}={value}\n')

def collect_released_versions():

    full_version_pattern = re.compile(r"\d+\.\d+(?:.\d+)?")
    major_version_pattern = re.compile(r"\d+\.\d+")

    gh_token=os.getenv(GITHUB_TOKEN)
    gh_env_repo = os.getenv(GITHUB_REPOSITORY)
    gh_owner = gh_env_repo.split('/')[0]
    gh_repo= gh_env_repo.split('/')[1]

    github = GhApi(owner='deckhouse', repo='deckhouse', token=gh_token)

    stable_version = None
    editions_reference = [ 'BE', 'CE', 'EE', 'FE', 'SE', 'SE-plus' ]
    channels = {
        'alpha': None,
        'beta': None,
        'early-access': None,
        'stable': None,
        'rock-solid': None
    }
    result_channels = {}

    def search_completion(editions):
        if (editions_reference != sorted(list(editions.keys()))):
            return None
        if (editions['FE'] and (list(editions.values())[:-1] == list(editions.values())[1:])):
            return editions
        else:
            return None 

    # collect all deployed versions for each channel
    for channel in channels.keys():
        workflow_runs = github.actions.list_workflow_runs(workflow_id=f'deploy-{channel}.yml')['workflow_runs']

        # iterate through workflow runs to collect all deployed channel versions
        for run in workflow_runs:
            editions = {}
            match_result = full_version_pattern.findall(run['head_branch'])
            if (len(match_result) < 1):
                continue
            version = match_result[0]
            jobs = github.actions.list_jobs_for_workflow_run(run['id'])['jobs']

            # skip run if deploy was failed
            deploy_status = 'success'
            for job in jobs:
                if (version in job['name'] and job['conclusion'] != 'success'):
                    deploy_status = job['conclusion']
            if (deploy_status != 'success'):
                continue
            
            # collect deployed versions for channel in one run
            for job in jobs:
                if ('Enable' in job['name']) and (job['conclusion'] == 'success'):
                    editions[job['name'].split()[1]] = version

            if ( channels[channel] == None ):
                channels[channel] = { version: editions }
            elif (version in channels[channel]):
                channels[channel][version] = channels[channel][version] | editions
            else:
                channels[channel][version] = editions
            result = search_completion(channels[channel][version])
            if (result):
                match_result = major_version_pattern.findall(version)
                if (len(match_result) < 1):
                    continue
                if ( channel == 'stable'):
                  stable_version = f'v{version}'
                result_channels[channel] = match_result[0]
                break
    yamldata = '''\
    groups:
    - name: "v1"
      channels:
        - name: alpha
          version: {alpha}
        - name: beta
          version: {beta}
        - name: ea
          version: {early-access}
        - name: stable
          version: {stable}
        - name: rock-solid
          version: {rock-solid}
    '''.format(**result_channels)

    print(yamldata)
    with open('ci/.helm/channels.yaml','w') as channels_file:
    # with open('channels.yaml','w') as channels_file:
        channels_file.write(yamldata)
        # yaml.dump(result_channels,channels_file)

    write_output('stable_version',stable_version)

def determine_clusters_needs_deploy ():
    kubeconf64 = os.getenv(ENV_KUBECONFIG64)
    if (kubeconf64 == None):
        print(f'Unable to load "{ENV_KUBECONFIG64}". Exit')
        exit(1)

    try:
        kubeconf = yaml.safe_load(base64.b64decode(kubeconf64).decode('utf-8'))
        config.load_kube_config_from_dict(kubeconf)
    except Exception as e:
        print(f'Unable to read KUBECONFIG: {ENV_KUBECONFIG64}')
        exit(1)

    v1 = client.CoreV1Api()
    print(f'Get configmap "{CM_NAME}"')
    try:
        cm = v1.read_namespaced_config_map(CM_NAME,CM_NAMESPACE)
    except:
        print(f'Unable to get configmap: {CM_NAME}')
        exit(1)
        
    if (yamldata == cm.data['channels.yaml']):
        write_output('dev_deploy',True)
    else:
        write_output('dev_deploy',False)

if __name__ == "__main__":
    try:
        collect_released_versions()
        determine_clusters_needs_deploy()
    except Exception as ex:
        print(ex)
        exit(1)