# -*- coding: utf-8 -*-
import pytest
import oauthist
from .conftest import (WEB_CALLBACK, setup_module, teardown_function,
                       fake_werkzeug_request)



#--- Test from_werkzeug

def test_from_werkzeug(web_client):
    request = fake_werkzeug_request(dict(response_type='code',
                                         client_id=web_client.id,
                                         redirect_uri=WEB_CALLBACK,
                                         scope='user_ro user_rw',
                                         state='1234'))
    req = oauthist.CodeRequest.from_werkzeug(request)
    assert not req.is_broken()
    assert not req.is_invalid()

    code = req.save_code()
    assert code.client_id == web_client.id
    assert code.redirect_uri == WEB_CALLBACK
    assert code.scope == 'user_ro user_rw'
    assert code.state == '1234'

#--- Test valid CodeRequest

def test_is_valid(web_client):
    req = oauthist.CodeRequest(client_id=web_client.id,
                               redirect_uri=WEB_CALLBACK,
                               scope='user_ro user_rw')
    assert not req.is_broken()
    assert not req.is_invalid()

#--- Test CodeRequest.is_broken

def test_missing_client_id(web_client):
    """ code request is invalid without client_id """
    req = oauthist.CodeRequest(redirect_uri='http://foo.com/bar',
                               scope='user_ro user_rw')
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
