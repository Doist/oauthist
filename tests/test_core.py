# -*- coding: utf-8 -*-
import oauthist

scopes = ['user_ro', 'user_rw', 'projects_ro', 'projects_rw']
oauthist.configure(prefix='tests', scopes=scopes)

#--- Setup/teardown functions


def setup_function(func):
    pass


def teardown_function(func):
    oauthist.full_cleanup()


#--- Helper functions

def pytest_funcarg__web_client(request):
    client = oauthist.Client(client_type='web',
                             redirect_urls=['http://web.example.com/oauth2cb', ])
    client.save()
    request.addfinalizer(client.delete)
    return client


def pytest_funcarg__ua_client(request):
    client = oauthist.Client(client_type='user-agent',
                            redirect_urls=['http://ua.example.com/oauth2cb', ])
    client.save()
    request.addfinalizer(client.delete)
    return client


def pytest_funcarg__native_client(request):
    client = oauthist.Client(client_type='native',
                             redirect_urls=['http://native.example.com/oauth2cb', ])
    client.save()
    request.addfinalizer(client.delete)
    return client


#--- Tests

def test_get_client(web_client):
    """
    Client.get() function does work
    """
    same_client = oauthist.Client.get(web_client._id)
    assert same_client == web_client


def test_client_attrs_set_get(web_client):
    """
    Client object can set and get attributes

    Attributes stored in the database on save() operation
    """
    name = 'my web client'
    web_client.set(name=name)
    web_client.save()
    same_client = oauthist.Client.get(web_client._id)
    assert same_client.name == name


def test_client_attrs_unset(web_client):
    """
    Client object can remove attributes
    """
    name = 'my web client'
    # attribute added
    web_client.set(name=name)
    web_client.save()
    # attribute removed
    web_client.unset('name')
    web_client.save()
    # nothing is stored in the database
    same_client = oauthist.Client.get(web_client._id)
    assert not 'name' in same_client.attrs

