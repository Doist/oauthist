# -*- coding: utf-8 -*-
import pytest
import oauthist
from .conftest import (WEB_CALLBACK, setup_module, teardown_function,
                       fake_werkzeug_request)
from oauthist import OauthistValidationError


def test_success(web_client):
    req = oauthist.CodeRequest(client_id=web_client._id,
                               redirect_uri=WEB_CALLBACK,
                               state='1234',
                               scope='user_ro user_rw')
    code = req.save_code()
    code.accept()

    exchange_req = oauthist.CodeExchangeRequest(
                            code=code._id,
                            client_id=web_client._id,
                            client_secret=web_client.client_secret,
                            redirect_uri=WEB_CALLBACK,
                            state='1234')
    access_token = exchange_req.exchange_for_token()
    assert access_token.get_json_content()['token_type'] == 'bearer'


def test_unable_to_exchange_code_twice(web_client):
    req = oauthist.CodeRequest(client_id=web_client._id,
                               redirect_uri=WEB_CALLBACK,
                               state='1234',
                               scope='user_ro user_rw')
    code = req.save_code()
    code.accept()

    # we can do it once
    exchange_req = oauthist.CodeExchangeRequest(
        code=code._id, client_id=web_client._id,
        client_secret=web_client.client_secret, redirect_uri=WEB_CALLBACK,
        state='1234')
    exchange_req.exchange_for_token()

    # but not twice
    exchange_req = oauthist.CodeExchangeRequest(
        code=code._id, client_id=web_client._id,
        client_secret=web_client.client_secret, redirect_uri=WEB_CALLBACK,
        state='1234')
    with pytest.raises(OauthistValidationError):
        exchange_req.exchange_for_token()


def test_code_unaccepted(web_client):
    """
    If code isn't explicitly accepted, refuse to exchange it to access token
    """
    req = oauthist.CodeRequest(client_id=web_client._id,
                               redirect_uri=WEB_CALLBACK,
                               state='1234',
                               scope='user_ro user_rw')
    code = req.save_code()

    exchange_req = oauthist.CodeExchangeRequest(
        code=code._id,
        client_id=web_client._id,
        client_secret=web_client.client_secret,
        redirect_uri=WEB_CALLBACK,
        state='1234')
    with pytest.raises(oauthist.OauthistValidationError):
        exchange_req.exchange_for_token()


@pytest.mark.parametrize('invalid_param', [
    'code', 'client_id', 'client_secret', 'redirect_uri', 'state'
])
def test_parameters_mismatch(web_client, invalid_param):
    """
    If some parameters in the code exchange request mismatch with same passed
    while receiving the code, raise exception
    """
    req = oauthist.CodeRequest(client_id=web_client._id,
                               redirect_uri=WEB_CALLBACK,
                               state='1234',
                               scope='user_ro user_rw')
    code = req.save_code()
    code.accept()

    params = {
        'code': code._id,
        'client_id': web_client._id,
        'client_secret': web_client.client_secret,
        'redirect_uri': WEB_CALLBACK,
        'state': '1234'
    }
    params.update(invalid_param='foo')
    exchange_req = oauthist.CodeExchangeRequest()
    with pytest.raises(oauthist.OauthistValidationError):
        exchange_req.exchange_for_token()
