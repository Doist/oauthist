# -*- coding: utf-8 -*-
import oauthist


WEB_CALLBACK = 'http://web.example.com/oauth2cb'
UA_CALLBACK = 'http://ua.example.com/oauth2cb'
NATIVE_CALLBACK = 'http://native.example.com/oauth2cb'

def setup_module():
    scopes = ['user_ro', 'user_rw', 'projects_ro', 'projects_rw']
    oauthist.configure(prefix='tests', scopes=scopes)


def teardown_function(func):
    oauthist.full_cleanup()


def pytest_funcarg__web_client(request):
    client = oauthist.Client(client_type='web',
                             redirect_urls=[WEB_CALLBACK, ])
    client.save()
    request.addfinalizer(client.delete)
    return client


def pytest_funcarg__ua_client(request):
    client = oauthist.Client(client_type='user-agent',
                             redirect_urls=[UA_CALLBACK, ])
    client.save()
    request.addfinalizer(client.delete)
    return client


def pytest_funcarg__native_client(request):
    client = oauthist.Client(client_type='native',
                             redirect_urls=[NATIVE_CALLBACK, ])
    client.save()
    request.addfinalizer(client.delete)
    return client


def fake_werkzeug_request(args=None, form=None):
    """
    Create fake request object

    :param args: dict of GET data
    :param form: dict of POST data
    """

    class Request(object): pass
    req = Request()
    req.form = form or {}
    req.args = args or {}
    return req
