# -*- coding: utf-8 -*-
import contextlib
import pytest
import oauthist
from tests.core import setup_function, teardown_function
from resources import resources
resources.register_mod('tests.resources_oauthist')


#--- Test from_werkzeug

@pytest.mark.fresh
def test_accept():
    with contextlib.nested(
        resources.client_ctx(),
        resources.werkzeug_code_request_ctx(),
    ):
        req = oauthist.CodeRequest.from_werkzeug(resources.werkzeug_code_request)
        assert not req.is_broken()

        code = req.save_code(user_id=resources.USER_ID)
        uri = code.accept()
        assert code.accepted
        assert uri == 'http://example.com/callback?code={0}&state={1}'.format(code.id, code.state)


def test_decline():
    with contextlib.nested(
        resources.client_ctx(),
        resources.werkzeug_code_request_ctx(),
    ):
        req = oauthist.CodeRequest.from_werkzeug(resources.werkzeug_code_request)
        assert not req.is_broken()

        code = req.save_code(user_id=resources.USER_ID)
        uri = code.decline()
        assert not code.accepted
        assert uri == 'http://example.com/callback?error=access_denied&state={0}'.format(code.state)



#--- Test CodeRequest.is_broken

def test_missing_client_id():
    """ code request is invalid without client_id """
    with contextlib.nested(
        resources.client_ctx(),
        resources.code_request_ctx(client_id=''),
    ):
    req = oauthist.CodeRequest.from_werkzeug(resources.werkzeug_code_request)
    assert req.is_broken()
    assert req.error == 'missing_client_id'


def test_missing_redirect_uri_valid(web_client):
    """ code request is valid without redirect uri, if there is no more
    variants"""
    req = oauthist.CodeRequest(client_id=web_client.id,
                               scope='user_ro user_rw')
    assert not req.is_broken()
    assert not req.is_invalid()
    assert req.redirect_uri == WEB_CALLBACK


def test_missing_redirect_uri_invalid(web_client):
    """ code request is invalid without redirect uri, if there is more than one
    redirect uri"""
    web_client.redirect_urls.append('http://foo.com/bar')
    web_client.save()
    req = oauthist.CodeRequest(client_id=web_client.id,
                               scope='user_ro user_rw')
    assert req.is_broken()
    assert req.error == 'missing_redirect_uri'


def test_invalid_redirect_url(web_client):

    req = oauthist.CodeRequest(client_id=web_client.id,
                               redirect_uri='http://foo.com/bar',
                               scope='user_ro user_rw')
    assert req.is_broken()
    assert req.error == 'invalid_redirect_url'


def test_invalid_redirect_url(web_client):
    req = oauthist.CodeRequest(client_id='1234',
                               redirect_uri='http://foo.com/bar',
                               scope='user_ro user_rw')
    assert req.is_broken()
    assert req.error == 'invalid_client_id'


#--- Test CodeRequest.is_invalid

def test_non_existent_scope(web_client):
    req = oauthist.CodeRequest(client_id=web_client.id, scope=None)
    assert req.is_invalid()
    assert req.error == 'missing_scope'

def test_scope_invalid(web_client):
    req = oauthist.CodeRequest(client_id=web_client.id, scope='user_ro invalid_scope')
    assert req.is_invalid()
    assert req.error == 'invalid_scope'

def test_scope_invalid_get_redirect_with_state(web_client):
    req = oauthist.CodeRequest(client_id=web_client.id, state='abcd',
                               scope='user_ro invalid_scope')
    assert req.is_invalid()
    assert req.get_redirect() == 'http://web.example.com/oauth2cb?error=invalid_scope&state=abcd'

def test_scope_invalid_get_redirect_without_state(web_client):
    req = oauthist.CodeRequest(client_id=web_client.id,
                               scope='user_ro invalid_scope')
    assert req.is_invalid()
    assert req.get_redirect() == 'http://web.example.com/oauth2cb?error=invalid_scope'


def test_scope_invalid_get_redirect_to_complex_uri(web_client):
    web_client.set(redirect_urls = ['http://web.example.com/router.php?page=oauth2cb#foo', ])
    web_client.save()
    req = oauthist.CodeRequest(client_id=web_client.id, state='abcd',
                               scope='user_ro invalid_scope')
    assert req.is_invalid()
    assert req.get_redirect() == ('http://web.example.com/router.php?'
                                  'page=oauth2cb&error=invalid_scope&state=abcd#foo')


#--- Test different sort of responses for valid clients

def test_is_valid(web_client):
    req = oauthist.CodeRequest(client_id=web_client.id,
                               redirect_uri=WEB_CALLBACK,
                               state='1234',
                               scope='user_ro user_rw')
    code = req.save_code(foo='bar')
    assert req.get_redirect() == ('http://web.example.com/oauth2cb?code=%s&'
                                  'state=1234' % code.id)
