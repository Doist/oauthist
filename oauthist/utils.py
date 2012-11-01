# -*- coding: utf-8 -*-
import re
import urlparse
import urllib

from oauthist.errors import OauthistValidationError

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


def check_url(url):
    """
    Validate string for URL
    """
    regex = re.compile(
        r'^https?://' # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|' #domain...
        r'localhost|' #localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})' # ...or ip
        r'(?::\d+)?' # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    if not regex.match(url):
        raise OauthistValidationError('%r is invalid URL' % url)
