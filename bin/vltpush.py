#!/usr/bin/env python


import sys
import subprocess
import os
import re

import git


def parse_status_line(line):
    line = line.strip()
    return re.split(r'\s+', line, maxsplit=1)


class Vlt(object):
    def __init__(self, jcr_root='.', cmd='vlt'):
        #vlt commands must be invoked under jcr_root
        self.jcr_root = os.path.abspath(jcr_root)

        #after executing vlt commands, it'll be chdir back to cwd.
        self.cwd = os.path.abspath('.')

        self.cmd = cmd


    def _exec(self, *args):
        cmd = (self.cmd,) + args
        return subprocess.Popen(cmd, stdout=subprocess.PIPE, stdin=subprocess.PIPE, stderr=subprocess.PIPE)

    def _exec_and_print(self, *args):
        os.chdir(self.jcr_root)
        p = self._exec(*args)
        print(p.args)
        os.chdir(self.cwd)
        return p

    def status(self, base_path='.'):
        os.chdir(self.jcr_root)

        base_path = os.path.abspath(base_path)
        p = self._exec('status', base_path)

        d = {
            'M': [],
            'A': [],
            'D': [],
            '?': [],
        }
        for line in p.stdout:
            status,file_path = parse_status_line(line)
            status = status[0] # only interested in the first character
            d.setdefault(status, []).append(os.path.join(base_path, file_path))

        os.chdir(self.cwd)
        return d

    def is_tracked(self, file_path):
        os.chdir(self.jcr_root)

        p = self._exec('info', file_path)
        tracked = False
        for line in p.stdout:
            if line.startswith('Status: '):
                _,info = line.split(':', 1)
                tracked = 'unknown' != info.strip()
                break
        os.chdir(self.cwd)

        return tracked

    def add(self, *file_paths):
        self._exec_and_print('add', *file_paths)

    def rm(self, *file_paths):
        self._exec_and_print('rm', *file_paths)
    
    def ci(self, *file_paths):
        self._exec_and_print('ci', *file_paths)



class Git(object):
    def __init__(self, repo_dir):
        self.repo = git.Repo(repo_dir)
        self.repo_dir = os.path.dirname(self.repo.git_dir)
        self.relpath_start_index = len(self.repo_dir) + 1

    def is_tracked(self, file_path):
        return len(self.repo.git.ls_files(file_path, z=True)) > 0

    def to_relative(self, file_path):
        if os.path.isabs(file_path):
            return file_path[self.relpath_start_index:]
        return file_path

    def untracked_under(self, file_path):
        rel_file_path = self.to_relative(file_path)
        start_index = len(rel_file_path) + 1
        return (x[start_index:] for x in self.repo.untracked_files if x.startswith(rel_file_path))

def main(argv):
    jcr_root = os.path.abspath(argv[1])
    
    g = Git(jcr_root)
    repo_dir = g.repo_dir

    vlt = Vlt()
    status = vlt.status()
    
    vlt_to_add = []
    for not_in_vlt in status['?']:
        if g.is_tracked(not_in_vlt):
            vlt_to_add.append(not_in_vlt)
    vlt_to_ci = status['M']

    vlt_to_rm = []
    for untracked in g.untracked_under(jcr_root):
        untracked_fullpath = os.path.join(jcr_root, untracked)
        if vlt.is_tracked(untracked_fullpath):
            vlt_to_rm.append(untracked_fullpath)


    for x in vlt_to_add:
        print('vlt add %s' % x)
    for x in vlt_to_rm:
        print('vlt rm %s' % x)
    for x in vlt_to_ci:
        print('vlt ci %s' % x)

    answer = raw_input('proceed? [Yn]> ')
    if not answer.lower().startswith('n'):
        vlt.add(*vlt_to_add)
        vlt.ci(*vlt_to_add)
        vlt.rm(*vlt_to_rm)
        vlt.ci(*vlt_to_rm)
        vlt.ci(*vlt_to_ci)



if __name__ == '__main__':
    main(sys.argv)
