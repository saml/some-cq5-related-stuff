'''CQ HTTP API

>>> cq = CQCurl(curl='curl', host='localhost', port=4502, cookie_path='/tmp/tmp.cookie')
>>> cq.url('/foo/bar')
'http://localhost:4502/foo/bar'
>>> cq.url('/foo/bar', params={'foo': 'bar'})
'http://localhost:4502/foo/bar?foo=bar'
>>> cq.url('/foo/bar', params={'foo': 'bar', 'hello': 'world'})
'http://localhost:4502/foo/bar?foo=bar&hello=world'


#>>> cq.login(dryrun=True)
#curl -f -s -F _charset_=utf-8 -c /tmp/tmp.cookie -F j_username=admin -F j_password=admin http://localhost:4502/libs/qa/core/content/login.html/j_security_check

'''

import json
import subprocess
import os
import itertools
import logging
import urllib
import re

log = logging.getLogger(__name__)

def append(l, *args):
    for x in args:
        l.append(x)

class CQCurl(object):
    TRAILING_JCR_CONTENT = re.compile(r'^(.*)/jcr:content$')

    def __init__(self, curl='curl', host='localhost', port=4502,
            username='admin', password='admin', cwd='/',
            cookie_path=None):

        self.curl = curl
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.cwd = cwd #current working directory
        self.json = None #current json. as a cache.

        if cookie_path is None:
            cookie_path = os.path.join(os.path.expanduser('~'), 'cqapi.%s@%s:%d.cookie' % (self.username, self.host, self.port))
        self.cookie_path = cookie_path

    def url(self, path, protocol='http://', host=None, port=None, params=None):
        '''path => url
         params dict is appended to url as GET params.'''

        if host is None:
            host = self.host
        if port is None:
            port = self.port
        if params is None:
            params = {}

        url = '%s%s:%d%s' % (protocol, host, port, path)

        param_list = []
        for k,v in params.iteritems():
            param_list.append('%s=%s' % (k,v))

        if len(param_list) > 0:
            url = '%s?%s' % (url, '&'.join(param_list))

        return urllib.quote(url, ';/?:@&=+$,')


    def _cmd(self, method='GET', use_cookie=True, headers=None):
        cmd = [self.curl, '-f', '-s']

        if use_cookie:
            append(cmd, '-b', self.cookie_path)

        if headers is None:
            headers = {}

        append(cmd, '-X', method)

        for k,v in headers.iteritems():
            append(cmd, '-H', '%s: %s' % (k,v))

        return cmd

    def _cmd_post(self, props=None, use_cookie=True, headers=None):
        cmd = self._cmd('POST', use_cookie=use_cookie, headers=headers)

        if props is not None:
            #this overrides Content-Type to application/x-www-form-urlencoded
            append(cmd, '-F', '_charset_=utf-8')

            for k,v in props.iteritems():
                append(cmd, '-F', '%s=%s' % (k, v))

        return cmd


    def _exec_command(self, cmd, dryrun=False):
        'executes cmd. returns (returncode, stdout, stderr)'
        if dryrun:
            print(' '.join(cmd))
            return (None, None, None)
        else:
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=False)
            out,err = p.communicate()
            return (p.returncode, out, err)

    def strip_jcr_content(self, jcr_path):
        match = self.TRAILING_JCR_CONTENT.match(jcr_path)
        if match is None:
            return jcr_path
        return match.group(1)

    def json_url(self, path, level=1, is_tidy=False):
        tidy_selector = '.tidy' if is_tidy else ''
        return self.url('%s%s.%d.json' % (path, tidy_selector, level))

    def get_json(self, path=None, level=1, is_tidy=False, encoding='utf-8', **kwargs):
        if path is None:
            path = self.cwd

        cmd = self._cmd()
        append(cmd, self.json_url(path, level, is_tidy))

        returncode,out,err = self._exec_command(cmd, **kwargs)

        d = json.loads(out, encoding=encoding)
        if path == self.cwd:
            self.json = d #update cache
        return d

    def login(self, **kwargs):
        if os.path.exists(self.cookie_path):
            #empty cookie if exists
            open(self.cookie_path, 'w').close()

        cmd = self._cmd(method='POST', use_cookie=False)
        append(cmd, '-c', self.cookie_path)
        append(cmd, '-F', 'j_username=' + self.username)
        append(cmd, '-F', 'j_password=' + self.password)
        append(cmd, self.url('/libs/qa/core/content/login.html/j_security_check'))

        return self._exec_command(cmd, **kwargs)

    def remove_page(self, page_path, **kwargs):
        cmd = self._cmd('POST')
        append(cmd, '-F', 'cmd=deletePage')
        append(cmd, '-F', 'force=false')
        append(cmd, '-F', 'path=' + page_path)
        append(cmd, self.url('/bin/wcmcommand'))

        return self._exec_command(cmd, **kwargs)

    def remove_pages(self, page_paths, **kwargs):
        cmd = self._cmd('POST')
        append(cmd, '-F', 'cmd=deletePage')
        append(cmd, '-F', 'force=false')

        for x in page_paths:
            append(cmd, '-F', 'path=' + x)

        append(cmd, self.url('/bin/wcmcommand'))

        return self._exec_command(cmd, **kwargs)

    def remove(self, path):
        cmd = self._cmd_post(props={':operation': 'delete'})
        append(cmd, self.url(path))
        return self._exec_command(cmd)

    def upload_image(self, file_path, target_dir_path, target_name=None, **kwargs):
        file_name = os.path.basename(file_path)

        if target_name is None:
            target_name = file_name

        cmd = self._cmd('POST')
        append(cmd, '-T', file_path)
        append(cmd, '-F', '*@TypeHint=nt:file')
        append(cmd, self.url('%s/%s' % (target_dir_path, target_name)))

        return self._exec_command(cmd, **kwargs)

    def pwd(self):
        return self.cwd

    def ls(self, path=None):
        if path is None:
            path = self.cwd

        path = os.path.join(self.cwd, path)

        l = []
        d = self.get_json(path)
        for k,v in d.iteritems():
            if isinstance(v, dict):
                l.append(k + '/')
            else:
                l.append(k)
        return l

    def cd(self, rel_path=None):
        if rel_path is None:
            return
        self.cwd = os.path.abspath(os.path.join(self.cwd, rel_path))
        self.json = None

    def req(self, path, method='GET', **kwargs):
        cmd = self._cmd(method)
        append(cmd, self.url(path))
        return self._exec_command(cmd, **kwargs)

    def create_node(self, path, primary_type='nt:unstructured', props=None, **kwargs):
        if props is None:
            props = {}

        cmd = self._cmd('POST')
        append(cmd, '-F', 'jcr:primaryType=' + primary_type)
        for k,v in props.iteritems():
            append(cmd, '-F', k + '=' + v)
        append(cmd, self.url(path))

        return self._exec_command(cmd, **kwargs)

    def create_folder(self, path, **kwargs):
        return self.create_node(path, primary_type='sling:Folder', **kwargs)


    def exists(self, path):
        cmd = self._cmd()
        append(cmd, self.json_url(path))
        ret,_,_ = self._exec_command(cmd)
        return ret == 0

    def mkdir(self, path, parents_too=False, **kwargs):
        path = os.path.join(self.cwd, path)
        if parents_too:
            cwd = ''
            parents,_ = os.path.split(path)
            for x in parents.split('/'):
                cwd += '/' + x
                if not self.exists(cwd):
                    self.create_folder(cwd)

        return self.create_folder(path, **kwargs)


    def propget(self, prop_name):
        if self.json is None:
            self.json = self.get_json()
        return self.json.get(prop_name)

    def propset(self, prop_name, value, path=None, **kwargs):
        if path is None:
            path = self.cwd
        props = {}
        props[prop_name] = value

        cmd = self._cmd_post(props)
        append(cmd, self.url(path))

        returncode,out,err = self._exec_command(cmd, **kwargs)

        if path == self.cwd:
            self.json = None

        return (returncode,out,err)

    def GET(self, path, params=None):
        '''Makes GET request to path.'''
        cmd = self._cmd()
        append(cmd, self.url(path, params=params))
        return self._exec_command(cmd)

    def GET_json(self, path, params=None):
        '''Makes GET request. Response body is assumed to be json.
        Returns None if response fails or response body is not json.'''
        cmd = self._cmd()
        append(cmd, self.url(path, params=params))
        return self.to_json(self._exec_command(cmd))

    def POST_json(self, path, headers=None, body=None):
        '''Makes POST request where body is json.
        If body starts with @, such as @../some.json,
        ../some.json is considered to be filesystem path from which json data is read from.'''

        if headers is None:
            headers = {'Content-Type': 'application/json'}

        cmd = self._cmd_post(props=None, headers=headers)

        if body is not None:
            append(cmd, '--data', body)

        append(cmd, self.url(path))

        return self.to_json(self._exec_command(cmd))
    
    def POST(self, path, headers=None, params=None):
        cmd = self._cmd_post(props=params, headers=headers)
        append(cmd, self.url(path))
        return self._exec_command(cmd)

    def to_json(self, command_result):
        '''returns json out of command result
        ex, to_json(GET('/tmp/hello.json'))

        does not update internal json cache used by ls()'''
        returncode,body,err = command_result
        if returncode != 0:
            return None

        return json.loads(body)


class CrxPackageManager(object):
    BASE_PATH = '/crx/packmgr/service/.json'

    def __init__(self, cq):
        self.cq = cq

    def list_packages(self, pred=(lambda x: True)):
        result = self.cq.GET_json('/.query.json', {'statement': "/jcr:root/etc/packages//*[@sling:resourceType = 'cq/packaging/components/pack']"})
        packages = []

        for x in result:
            path = self.cq.strip_jcr_content(x['jcr:path'])
            if pred(path):
                packages.append()

        return packages
    
    def _manager_path(self, jcr_path):
        return self.BASE_PATH + jcr_path


    def exec_cmd(self, cmd, jcr_path, params=None):
        if params is None:
            params = {}
        params['cmd'] = cmd
        return self.cq.to_json(self.cq.POST(self._manager_path(jcr_path), params=params))

    def delete(self, jcr_path):
        return self.exec_cmd('delete', jcr_path)

    def uninstall(self, jcr_path):
        return self.exec_cmd('uninstall', jcr_path)

    def install(self, jcr_path):
        return self.exec_cmd('install', jcr_path)

    def upload(self, file_path):
        return self.exec_cmd('upload', '/', params={'package': '@' + file_path})


