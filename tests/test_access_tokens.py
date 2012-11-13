# -*- coding: utf-8 -*-
import pytest
import oauthist
from .conftest import (WEB_CALLBACK, setup_module, teardown_function,
                       fake_werkzeug_request)
from oauthist import AccessToken


def pytest_funcarg__access_token(request):
    token = AccessToken(scope='foo bar baz')
    token.save()
    request.addfinalizer(token.delete)
    return token


def test_non_existent_access_token(access_token):
    with pytest.raises(oauthist.InvalidAccessToken):
        oauthist.check_access_token('foo')


def test_valid_token_no_scopes(access_token):
    received = oauthist.check_access_token(access_token._id)
    assert received == access_token

def test_token_valid_for_one_scope(access_token):
    oauthist.check_access_token(access_token._id, 'foo', 'spam')


def test_token_invalid_for_all_tokens(access_token):
    with pytest.raises(oauthist.InvalidAccessToken):
        oauthist.check_access_token(access_token._id, 'spam', 'egg')


def test_from_werkzeug_header_valid(access_token):
    req = fake_werkzeug_request(headers={'Authorization': 'Bearer %s' % access_token._id})
    token_string = oauthist.access_token_from_werkzeug(req)
    assert token_string is not None
    oauthist.check_access_token(token_string, 'foo')


def test_from_werkzeug_unrecognized_header(access_token):
    req = fake_werkzeug_request(headers={'Authorization': 'Foo %s' % access_token._id})
    token_string = oauthist.access_token_from_werkzeug(req)
    assert token_string is None


def test_from_werkzeug_form_valid(access_token):
    req = fake_werkzeug_request(form={'access_token': access_token._id})
    token_string = oauthist.access_token_from_werkzeug(req)
    assert token_string is not None
    oauthist.check_access_token(token_string, 'foo')


def test_from_werkzeug_args_valid(access_token):
    req = fake_werkzeug_request(args={'access_token': access_token._id})
    token_string = oauthist.access_token_from_werkzeug(req)
    assert token_string is not None
    oauthist.check_access_token(token_string, 'foo')


def test_from_werkzeug_more_than_one_way_of_sending_parameter(access_token):
    req = fake_werkzeug_request(
        form={'access_token': access_token._id},
        args={'access_token': access_token._id})
    token_string = oauthist.access_token_from_werkzeug(req)
    assert token_string is None
