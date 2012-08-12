#!/usr/bin/env python

import sys
import os
import re


class Log(object):
    REQUEST = re.compile(r'^(.+) \[(\d+)\] -> (.+)$')
    RESPONSE = re.compile(r'^(.+) \[(\d+)\] <- (.+) (\d+ms)$')
    def __init__(self, line):
        m = self.REQUEST.match(line)
        if m:
            self.timestamp = m.group(1)
            self.request_id = int(m.group(2), 10)
            self.request_line = m.group(3)
            self.response_time = None
        else:
            m = self.RESPONSE.match(line)
            if m:
                self.timestamp = m.group(1)
                self.request_id = int(m.group(2), 10)
                self.request_line = m.group(3)
                self.response_time = m.group(4)



responses = {}
while True:
    x = Log(sys.stdin.readline().strip())
    k = x.request_id
    if k is not None:
        v = responses.get(k, None)
        if v is not None:
            print('%s %s\n\t(%s ~ %s)' % (x.response_time, v.request_line, v.timestamp, x.timestamp))
            del responses[k]
        else:
            responses[k] = x

