#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: Contributors to the esp.bitbucket project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: bitbucket_hook_info
short_description: Get information about Hooks in Bitbucket Server
description:
- Manages Hooks on Bitbucket Server.
- Authentication can be done with I(token) or with I(username) and I(password).
author:
  - Björn Oscarsson
version_added: 1.5.0
options:
  url:
    description:
    - Bitbucket Server URL.
    type: str
    required: false
  username:
    description:
    - Username used for authentication.
    - This is only needed when not using I(token).
    - Required when I(password) is provided.
    type: str
    required: false
    aliases: [ user ]
  password:
    description:
    - Password used for authentication.
    - This is only needed when not using I(token).
    - Required when I(username) is provided.
    type: str
    required: false
  token:
    description:
    - Token parameter for authentication.
    - This is only needed when not using I(username) and I(password).
    type: str
    required: false
  repository:
    description:
    - Repository name.
    type: str
    required: true
  project_key:
    description:
    - Bitbucket project key.
    type: str
    required: true
    aliases: [ project ]
  hook_id:
    description:
    - Bitbucket hook ID.
    type: str
    required: true
  settings:
    description:
    - Bitbucket Hook settings.
    type: str
    required: true
  state:
    description:
    - Whether the hook should be enabled or not.
    type: str
    default: enabled
    choices: [ enabled, disabled, inherited ]
    required: false
  return_content:
    description:
      - Whether or not to return the body of the response as a "content" key in
        the dictionary result no matter it succeeded or failed.
    type: bool
    default: true
  validate_certs:
    description:
      - If C(no), SSL certificates will not be validated.
      - This should only set to C(no) used on personally controlled sites using self-signed certificates.
    type: bool
    default: yes
  use_proxy:
    description:
      - If C(no), it will not use a proxy, even if one is defined in an environment variable on the target hosts.
    type: bool
    default: yes
  sleep:
    description:
      - Number of seconds to sleep between API retries.
    type: int
    default: 5
  retries:
    description:
      - Number of retries to call Bitbucket API URL before failure.
    type: int
    default: 3
notes:
- Bitbucket Access Token can be obtained from Bitbucket profile -> Manage Account -> Personal Access Tokens.
- Supports C(check_mode).
'''

EXAMPLES = r'''
- name: Enable Hook
  esp.bitbucket.bitbucket_hook:
    url: 'https://bitbucket.example.com'
    username: jsmith
    password: secrect
    repository: bar
    project_key: FOO
    hook_id: com.nerdwin15.stash-stash-webhook-jenkins:jenkinsPostReceiveHook
    settings: "{{ _settings | to_json }}"
    state: "enabled"
    validate_certs: no
  vars:
    _settings:
      { 'key': 'value' }
'''

import json
from ansible.module_utils.basic import AnsibleModule
from ansible_collections.esp.bitbucket.plugins.module_utils.bitbucket import BitbucketHelper

def update_hook(module, bitbucket):
    state = module.params['state']
    hook_endpoint = 'hook'
    if (bitbucket.module.params['repository'] == ''):
        hook_endpoint = 'hook-project'
    info = None
    content = None

    if (state == "enabled"):
      data = None
      try:
          data = json.loads(module.params['settings'])
          if isinstance(data, dict):
              content = data
          else:
              bitbucket.module.fail_json(msg='settings parameter does not provide a valid JSON formatted string.', settings=module.params['settings'])
      except ValueError as e:
          bitbucket.module.fail_json(msg='settings parameter does not provide a valid JSON formatted string. (value exception)', settings=module.params['settings'])

      info, content = bitbucket.request(
          api_url=(bitbucket.BITBUCKET_API_ENDPOINTS[hook_endpoint] + '/settings').format(
              url=bitbucket.module.params['url'],
              projectKey=bitbucket.module.params['project_key'],
              repositorySlug=bitbucket.module.params['repository'],
              hookId=module.params['hook_id'],
          ),
          method='PUT',
          data=data,
      )
      info_enabled, content_enabled = bitbucket.request(
          api_url=(bitbucket.BITBUCKET_API_ENDPOINTS[hook_endpoint] + '/enabled').format(
              url=bitbucket.module.params['url'],
              projectKey=bitbucket.module.params['project_key'],
              repositorySlug=bitbucket.module.params['repository'],
              hookId=module.params['hook_id'],
          ),
          method='PUT',
      )
    elif (state == "disabled"):
      info, content = bitbucket.request(
          api_url=(bitbucket.BITBUCKET_API_ENDPOINTS[hook_endpoint] + '/enabled').format(
              url=bitbucket.module.params['url'],
              projectKey=bitbucket.module.params['project_key'],
              repositorySlug=bitbucket.module.params['repository'],
              hookId=module.params['hook_id'],
          ),
          method='DELETE',
      )
    elif (state == "inherited"):
      if (bitbucket.module.params['repository'] != ''):
        info, content = bitbucket.request(
            api_url=(bitbucket.BITBUCKET_API_ENDPOINTS['hook']).format(
                url=bitbucket.module.params['url'],
                projectKey=bitbucket.module.params['project_key'],
                repositorySlug=bitbucket.module.params['repository'],
                hookId=module.params['hook_id'],
            ),
            method='DELETE',
        )
      else:
        bitbucket.module.fail_json(msg='Cannot use state `inherited` when repository is not set.')

    if info['status'] in [200,201]:
        content.pop('fetch_url_retries', None)
        return content, True

    if info['status'] == 401:
        bitbucket.module.fail_json(
            msg='The currently authenticated user has insufficient permissions to read `{repositorySlug}` repository.'.format(
                repositorySlug=bitbucket.module.params['repository'],
            ))

    if info['status'] == 404:
        bitbucket.module.fail_json(msg='Project `{projectKey}` or repository `{repositorySlug}` does not exist.'.format(
            projectKey=bitbucket.module.params['project_key'],
            repositorySlug=bitbucket.module.params['repository'],
        ))

    if info['status'] != 200:
        bitbucket.module.fail_json(
            msg='Failed to update hook setting for projectKey `{projectKey}` and repositorySlug `{repositorySlug}`: {info}'.format(
                projectKey=bitbucket.module.params['project_key'],
                repositorySlug=bitbucket.module.params['repository'],
                info=info,
            ))

    return content, False

def main():
    argument_spec = BitbucketHelper.bitbucket_argument_spec()
    argument_spec.update(
        repository=dict(type='str', default='', no_log=False),
        project_key=dict(type='str', required=True, no_log=False, aliases=['project']),
        hook_id=dict(type='str', required=True, aliases=['hid']),
        state=dict(type='str', choices=['enabled', 'disabled', 'inherited'], default='enabled'),
        settings=dict(type='str', default=''),
    )
    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
        required_together=[('username', 'password')],
        required_one_of=[('username', 'token')],
        mutually_exclusive=[('username', 'token')]
    )

    bitbucket = BitbucketHelper(module)

    # Seed the result dict in the object
    result = dict(
        changed=False,
        project_key=module.params['project_key'],
        repository=module.params['repository'],
        hook_id=module.params['hook_id'],
        state=module.params['state'],
        messages=[],
        json={},
    )

    # Retrieve existing webhooks information (if any)
    content = {}
    changed = True
    if not module.check_mode:
      content, changed = update_hook(module, bitbucket)
    result['json'] = content
    result['changed'] = changed

    module.exit_json(**result)

if __name__ == '__main__':
    main()