#!/usr/bin/env python

from ghapi.all import *
import os
import re
from kubernetes import client, config
import yaml
import base64
import sys

GITHUB_TOKEN=os.getenv('GITHUB_TOKEN')
if (GITHUB_TOKEN == None):
    print("GITHUB_TOKEN env variable was not found. Terminated.")
    exit(1)

GITHUB_OWNER, GITHUB_REPO = os.getenv('GITHUB_REPOSITORY').split('/')

KUBECONF_NAME_PREFIX = 'KUBECONFIG_BASE64_'
CM_NAME = 'release-channels-data'

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
'''
result_channels = {}
stable_version = None

def write_output(var,value):
    with open(os.getenv('GITHUB_OUTPUT'), 'a') as output:
        output.write(f'{var}={value}\n')

def collect_released_versions():
    global stable_version
    full_version_pattern = re.compile(r"\d+\.\d+(?:.\d+)?")
    major_version_pattern = re.compile(r"\d+\.\d+")

    github = GhApi(owner='deckhouse', repo='deckhouse', token=GITHUB_TOKEN)

    editions_reference = [ 'BE', 'CE', 'EE', 'FE', 'SE', 'SE-plus' ]
    channels = {
        'alpha': None,
        'beta': None,
        'early-access': None,
        'stable': None,
        'rock-solid': None
    }

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
    data = yamldata.format(**result_channels)

    print(data)
    with open('ci/.helm/channels.yaml','w') as channels_file:
    # with open('channels.yaml','w') as channels_file:
        channels_file.write(data)
        # yaml.dump(result_channels,channels_file)

    write_output('stable_version',stable_version)

def determine_clusters_need_deploy (kubeconf_name,kubeconf64):
    output_prefix = 'DEPLOY_'

    try:
        kubeconf = yaml.safe_load(base64.b64decode(kubeconf64).decode('utf-8'))
        config.load_kube_config_from_dict(kubeconf)
    except:
        print(f'::warning file=scripts/{os.path.basename(__file__)},::Unable to load "{kubeconf_name}". Cluster {kubeconf_name} will be skipped.')
        # print(f'Unable to load "{kubeconf_name}". Cluster {kubeconf_name} will be skipped."')
        write_output(output_prefix+kubeconf_name,'false')
        return
    
    namespace = os.getenv(f'NAMESPACE_{kubeconf_name}')

    v1 = client.CoreV1Api()
    try:
        cm = v1.read_namespaced_config_map(CM_NAME,namespace)
    except Exception as e:
        print(f'Unable to get configmap "{CM_NAME}" in namespace "{namespace}. Cluster {kubeconf_name} will be skipped.\nError: {e}"')
        write_output(output_prefix+kubeconf_name,'false')
        return
    data = yamldata.format(**result_channels)
    if (data != cm.data['channels.yaml']):
        write_output(output_prefix+kubeconf_name,'true')
    else:
        write_output(output_prefix+kubeconf_name,'false')

def determine_release_id():
    github = GhApi(owner='himax1991', repo='test', token=GITHUB_TOKEN)
    write_output('target_release_id',github.repos.get_release_by_tag(tag=stable_version)['id'])
    write_output('latest_release_id',github.repos.get_latest_release()['id'])

if __name__ == "__main__":
    collect_released_versions()

    kubecfgs = {}
    for key,value in os.environ.items():
        if key.startswith(KUBECONF_NAME_PREFIX):
            kubecfgs |= {key:value}
    for item,value in kubecfgs.items():
      determine_clusters_need_deploy(item,value)

    determine_release_id()
