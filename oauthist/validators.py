# -*- coding: utf-8 -*-
import re
from oauthist.errors import OauthistValidationError

CLIENT_TYPES = ('web', 'user-agent', 'native')
CONFIDENTIAL_CLIENTS = ('web', )
PUBLIC_CLIENTS = ('user-agent', 'native')


def check_client_type(client_type):
    """
    validate client type string.

    Supported valies: "web", "user-agent", "native"
    """
    if client_type not in CLIENT_TYPES:
        raise OauthistValidationError('Supported client types: %s' % CLIENT_TYPES)


def check_redirect_url(redirect_url):
    """
    Validate redirect URL

    :param redirect_url: string or list of strings representing URLs to redirect
                         to
    """
    if isinstance(redirect_url, basestring):
        urls = [redirect_url, ]
    else:
        urls = redirect_url
    for url in urls:
        check_url(url)


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
