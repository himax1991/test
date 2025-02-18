#!/usr/bin/env python

from ghapi.all import *
from pprint import pprint
from time import sleep
import json
import os

gh_token=os.getenv('GITHUB_TOKEN')

github = GhApi(owner='deckhouse', repo='deckhouse', token=gh_token)

channels = {
    # 'alpha': None,
    # 'beta': None,
    # 'early-access': None,
    'stable': None
    # 'rock-solid': None
}


for channel in channels.keys():
    editions = {
        'FE': None,
        'SE': None,
        'SE-plus': None,
        'EE': None,
        'CE': None,
        'BE': None,
    }
    workflow_runs = github.actions.list_workflow_runs(workflow_id=f'deploy-{channel}.yml')['workflow_runs']
    for run in workflow_runs:
        version = run['head_branch']
        jobs = github.actions.list_jobs_for_workflow_run(run['id'])['jobs']
        # if ('stable' in run['name']):
        #   print(f'Workflow run name: {run['name']}, version: {version}')
        #   sleep(0.3)
        for job in jobs:
            if ('Enable' in job['name']) and (job['conclusion'] == 'success'):
                editions[job['name'].split()[1]] = version
        if editions['FE'] and (list(editions.values())[:-1] == list(editions.values())[1:]):
            break
    channels[channel] = editions['FE']

data = {
    'alpha': channels['alpha'].split('.')[0] + '.' + channels['alpha'].split('.')[1],
    'beta': channels['beta'].split('.')[0] + '.' + channels['beta'].split('.')[1],
    'ea': channels['early-access'].split('.')[0] + '.' + channels['early-access'].split('.')[1],
    'stable': channels['stable'].split('.')[0] + '.' + channels['stable'].split('.')[1],
    'rock-solid': channels['rock-solid'].split('.')[0] + '.' + channels['rock-solid'].split('.')[1]
}
yamldata = '''\
groups:
 - name: "v1"
   channels:
    - name: alpha
      version: {alpha}
    - name: beta
      version: {beta}
    - name: ea
      version: {ea}
    - name: stable
      version: {stable}
    - name: rock-solid
      version: {rock-solid}
'''.format(**data)

print(yamldata)
# with open('ci/.helm/channels.yaml','w') as channels_file:
#     channels_file.write(yamldata)
