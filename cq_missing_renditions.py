#!/usr/bin/env python

import cqapi

import argparse
import os
import getpass
import sys
import re

def walk_filtering_by(cq, jcr_path, pred, recurse=True):
    '''walks jcr_path filtering by pred
    when recurse is set, only recurses down nodes where pred(node_path, node_properties) is False'''
    to_visit = [jcr_path]

    while len(to_visit) > 0:
        curr_path = to_visit.pop()
        for node_name,props in cq.get_json(curr_path).iteritems():
            node_path = os.path.join(curr_path, node_name)
            
            if pred(node_path, props):
                yield (node_path, props)
            elif recurse and hasattr(props, 'keys'):
                to_visit.append(node_path)


def walk(cq, jcr_path, recurse=True):
    to_visit = [jcr_path]

    while len(to_visit) > 0:
        curr_path = to_visit.pop()
        for node_name,props in cq.get_json(curr_path).iteritems():
            node_path = os.path.join(curr_path, node_name)
            
            if recurse and hasattr(props, 'keys'):
                to_visit.append(node_path)

            yield (node_path, props)



def filter(cq, jcr_path, pred, recurse=True):
    for node_path,props in walk(cq, jcr_path, recurse=recurse):
        if pred(node_path, props):
            yield (node_path, props)


def is_dam_asset(node_path, props):
    try:
        return 'dam:Asset' == props['jcr:primaryType']
    except:
        return False

def is_rendition(node_path, props):
    try:
        return 'nt:file' == props['jcr:primaryType']
    except:
        return False

def get_renditions_under(cq, dam_path, recurse=True):
    for asset_path,props in walk_filtering_by(cq, dam_path, pred=is_dam_asset, recurse=recurse):
        for rendition_path,rendition_props in walk_filtering_by(cq, os.path.join(asset_path, 'jcr:content/renditions'), pred=is_rendition, recurse=False):
            yield (rendition_path, rendition_props)
    

def find_missing_renditions(src_renditions, cq_target, dam_folder_path, recurse=True):
    target_renditions = set()
    for rendition_path,_ in get_renditions_under(cq_target, dam_folder_path, recurse=recurse):
        target_renditions.add(rendition_path)

    return src_renditions - target_renditions

def parse_instance_spec(spec, regex=re.compile(r'^([^@:]+)@([^@:]+):(\d+)$')):
    m = regex.match(spec)
    if m:
        return (m.group(1), m.group(2), int(m.group(3)))
    return (None,None,None)

def parse_hostport(hostport, regex=re.compile(r'^([^:]+):(\d+)$')):
    m = regex.match(hostport)
    return (m.group(1), int(m.group(2), 10))


def main(argv):
    parser = argparse.ArgumentParser(description='finds missing renditions', prog=argv[0])
    parser.add_argument('dampath', help='dam folder path')
    parser.add_argument('author', help='author instance spec. username@host:port')
    parser.add_argument('publish', nargs='+', help='publish instance spec. host:port')
    args = parser.parse_args(argv[1:])

    username,host,port = parse_instance_spec(args.author)
    password = getpass.getpass(prompt='Password for %s [default=admin]> ' % args.author)
    if not password:
        password = 'admin'

    cq_author = cqapi.CQCurl(username=username, password=password, host=host, port=port)
    cq_author.login()

    cq_publishes = []
    for hostport in args.publish:
        host,port = parse_hostport(hostport)
        username = 'anonymous'
        password = 'anonymous'
        cq = cqapi.CQCurl(username=username, password=password, host=host, port=port)
        cq_publishes.append(cq)
        cq.login()

    sys.stderr.write('getting rendition list under %s%s\n' % (cq_author.host, args.dampath))
    src_renditions = set()
    for rendition_path,_ in get_renditions_under(cq_author, args.dampath):
        src_renditions.add(rendition_path)
    sys.stderr.write('total %d renditions\n' % len(src_renditions))

    for cq_publish in cq_publishes:
        sys.stderr.write('finding missing renditions under %s%s\n' % (cq_publish.host, args.dampath))
        for x in find_missing_renditions(src_renditions, cq_publish, args.dampath):
            print('http://%s:%d%s' % (cq_publish.host, cq_publish.port, x))


if __name__ == '__main__':
    import datetime
    t = datetime.datetime.now()
    main(sys.argv)
    sys.stderr.write('took: %s\n' % (datetime.datetime.now() - t))
