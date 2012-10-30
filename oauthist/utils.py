# -*- coding: utf-8 -*-
import urlparse
import urllib



def add_arguments(url, args):
    """
    Add GET arguments to the URL in the most correct way

    For example

    .. code-block:: python

       >>> add_arguments('http://example.com/foo.php?1=2', [(3, 4)])
       'http://example.com/foo.php?1=2&3=4'
    """
    chunks = list(urlparse.urlparse(url))
    qs = urlparse.parse_qsl(chunks[4])
    qs += args
    chunks[4] = urllib.urlencode(qs)
    return urlparse.urlunparse(chunks)
