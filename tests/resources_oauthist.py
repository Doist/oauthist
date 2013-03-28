# -*- coding: utf-8 -*-
import oauthist
from resources import resources

resources.REDIRECT_URI = 'http://example.com/callback'
resources.SCOPE = 'user_ro user_rw'
resources.STATE = '1234'
resources.USER_ID = 1


@resources.register_func
def client(redirect_urls=None):
    """
    Create OAuth 2.0 client
    :param redirect_urls: list of strings with redirect urls, or None to use default value
    """
    if redirect_urls is None:
        redirect_urls = [resources.REDIRECT_URI]
    client = oauthist.Client(redirect_urls=redirect_urls)
    client.save()
    try:
        yield client
    finally:
        client.delete()


@resources.register_func
def werkzeug_request(args=None, form=None, headers=None):
    """
    Create fake werkzeug request object

    :param args: dict of GET data
    :param form: dict of POST data
    :param headers: dict of HTTP headers
    """
    yield Request(args, form, headers)


@resources.register_func
def werkzeug_code_request(client_id=None, redirect_uri=resources.REDIRECT_URI,
                          scope=resources.SCOPE, state=resources.STATE):
    """
    Create werkzeug code request
    """
    args = {
        'response_type': 'code',
        'client_id': client_id is None and resources.client.id or client_id,
        'redirect_uri': redirect_uri,
        'scope': scope,
        'state': state,
    }
    yield Request(args=args)


class Request(object):
    def __init__(self, args=None, form=None, headers=None):
        self.args = args or {}
        self.form = form or {}
        self.headers = headers or {}
