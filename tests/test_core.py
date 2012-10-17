# -*- coding: utf-8 -*-
from oauthist import Framework

scopes = ['user_ro', 'user_rw', 'projects_ro', 'projects_rw']
oauthist = Framework(prefix='tests', scopes=scopes)

#--- Setup/teardown functions


def setup_function(func):
    pass


def teardown_function(func):
    oauthist.full_cleanup()


#--- Helper functions

def pytest_funcarg__web_client(request):
    client = oauthist.register_client('web',
                                      'http://web.example.com/oauth2cb')
    request.addfinalizer(client.delete)
    return client


def pytest_funcarg__ua_client(request):
    client = oauthist.register_client('user-agent',
                                      'http://ua.example.com/oauth2cb')
    request.addfinalizer(client.delete)
    return client


def pytest_funcarg__native_client(request):
    client = oauthist.register_client('native',
                                      'http://native.example.com/oauth2cb')
    request.addfinalizer(client.delete)
    return client


#--- Tests

def test_get_client(web_client):
    """
    get_client() function does work
    """
    same_client = oauthist.get_client(web_client.id)
    assert same_client == web_client


def test_client_attrs_set_get(web_client):
    """
    Client object can set and get attributes

    Attributes stored in the database on save() operation
    """
    name = 'my web client'
    web_client.attrs['name'] = name
    web_client.save()
    same_client = oauthist.get_client(web_client.id)
    assert same_client.attrs['name'] == name


def test_client_attrs_del(web_client):
    """
    Client object can remove attributes
    """
    name = 'my web client'
    # attribute added
    web_client.attrs['name'] = name
    web_client.save()
    # attribute removed
    del web_client.attrs['name']
    web_client.save()
    # nothing is stored in the database
    same_client = oauthist.get_client(web_client.id)
    assert not 'name' in same_client.attrs

