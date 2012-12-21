# -*- coding: utf-8 -*-
import sys

#--- py3k compatibility (copied and inspired by six)
PY3 = sys.version_info[0] == 3
if PY3:
    from urllib.parse import urlparse, urlunparse, urlencode, parse_qsl
    xrange = range
    text = str
    binary = bytes
    def b(s):
        return s.encode("latin-1")
else:
    from urlparse import urlparse, urlunparse, parse_qsl
    from urllib import urlencode
    xrange = xrange
    text = unicode
    binary = str
    def b(s):
        return str(s)

def u(b):
    if isinstance(b, binary):
        return b.decode('latin-1')
    return b
