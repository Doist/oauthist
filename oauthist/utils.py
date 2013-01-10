# -*- coding: utf-8 -*-
import re
from oauthist.compat import urlparse, urlencode, parse_qsl, urlunparse
from oauthist.errors import OauthistValidationError

def add_arguments(url, args):
    """
    Add GET arguments to the URL in the most correct way

    For example

    .. code-block:: python

       >>> add_arguments('http://example.com/foo.php?1=2', [(3, 4)])
       'http://example.com/foo.php?1=2&3=4'
    """
    chunks = list(urlparse(url))
    qs = parse_qsl(chunks[4])
    qs += args
    chunks[4] = urlencode(qs)
    return urlunparse(chunks)


def add_fragment(url, args):
    """
    Add hash URL fragment in the most correct way by replacing the current one
    (if any).
    """
    chunks = list(urlparse(url))
    chunks[5] = urlencode(args)
    return urlunparse(chunks)


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
