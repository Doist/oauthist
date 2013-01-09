# -*- coding: utf-8 -*-
"""
Testing Resource Owner Password Credentials Grant
"""
import pytest
import oauthist
from .conftest import (WEB_CALLBACK, setup_module, teardown_function,
                       fake_werkzeug_request)
from oauthist import OauthistValidationError, PasswordExchangeRequest


#--- two "verify_request" implementations

def success(username, password):
    return {'user_id': 1}


def fail(username, password):
    return None


def http_request(client, *rm_attrs, **attrs):
    """
    return fake http request without attributes marked as rm_attrs, and
    with extra attributes, passed as attrs
    """
    form_attrs = {
        'username': 'user1',
        'password': 'password',
        'client_id': client.id,
        'client_secret': client.client_secret,
        'grant_type': 'password',
    }
    form_attrs.update(attrs)
    for key in rm_attrs:
        form_attrs.pop(key)
    return fake_werkzeug_request(form=form_attrs)


def test_success(web_client):
    req = PasswordExchangeRequest.from_werkzeug(http_request(web_client),
                                                verify_requisites=success)
    access_token = req.exchange_for_token()
    assert access_token.username == 'user1'
    assert access_token.user_id == 1
    assert access_token.client_id == web_client.id


def test_anonymous_request(web_client):
    # delete client_id and client_secret from request
    request = http_request(web_client, 'client_id', 'client_secret')
    req = PasswordExchangeRequest.from_werkzeug(request,
                                                verify_requisites=success)
    assert req.is_invalid()
    req = PasswordExchangeRequest.from_werkzeug(request,
                                                verify_requisites=success,
                                                client_required=False)
    assert not req.is_invalid()


def test_wrong_client_id(web_client):
    request = http_request(web_client, client_id='123')
    req = PasswordExchangeRequest.from_werkzeug(request,
                                                verify_requisites=success)
    assert req.is_invalid()


def test_wrong_password(web_client):
    request = http_request(web_client, client_secret='123')
    req = PasswordExchangeRequest.from_werkzeug(request,
                                                verify_requisites=success)
    assert req.is_invalid()


def test_with_public_clients(ua_client):
    request = http_request(ua_client, 'client_secret')
    req = PasswordExchangeRequest.from_werkzeug(request,
                                                verify_requisites=success)
    assert req.is_invalid()
    req = PasswordExchangeRequest.from_werkzeug(request,
                                                verify_requisites=success,
                                                client_secret_required=False)
    assert not req.is_invalid()
