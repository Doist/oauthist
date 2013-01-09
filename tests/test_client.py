# -*- coding: utf-8 -*-
import pytest
import oauthist
from oauthist import OauthistValidationError
from .conftest import WEB_CALLBACK, setup_module, teardown_function


def test_client_without_redirect_urls_is_invalid(web_client):
    """
    If there is not redirect_urls, client cannot be saved
    """
    web_client.attrs['redirect_urls'] = []
    with pytest.raises(OauthistValidationError):
        web_client.save()


def test_get_client(web_client):
    """
    Client.get() function does work
    """
    same_client = oauthist.Client.objects.get(web_client.id)
    assert same_client == web_client


def test_client_attrs_set_get(web_client):
    """
    Client object can set and get attributes

    Attributes stored in the database on save() operation
    """
    name = 'my web client'
    web_client.set(name=name)
    web_client.save()
    same_client = oauthist.Client.objects.get(web_client.id)
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
    same_client = oauthist.Client.objects.get(web_client.id)
    assert not 'name' in same_client.attrs
