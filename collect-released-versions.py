#!/usr/bin/env python

from ghapi.all import *
import os
import re

full_version_pattern = re.compile(r"\d+\.\d+(?:.\d+)?")
major_version_pattern = re.compile(r"\d+\.\d+")

gh_token=os.getenv('GITHUB_TOKEN')

github = GhApi(owner='deckhouse', repo='deckhouse', token=gh_token)

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
        version = full_version_pattern.findall(run['head_branch'])[0]
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
            result_channels[channel] = major_version_pattern.findall(version)[0]
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

# print(yamldata)
with open('ci/.helm/channels.yaml','w') as channels_file:
    channels_file.write(yamldata)
    # yaml.dump(result_channels,channels_file)
