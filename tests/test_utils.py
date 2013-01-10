# -*- coding: utf-8 -*-
import pytest
from oauthist.utils import *


@pytest.mark.parametrize(('url', 'expected_result'), [
    ('http://example.com/foo.php', 'http://example.com/foo.php?3=4'),
    ('http://example.com/foo.php?1=2', 'http://example.com/foo.php?1=2&3=4'),
    ('http://example.com/foo.php?3=1', 'http://example.com/foo.php?3=1&3=4'),
    ])
def test_add_arguments(url, expected_result):
    """
    Add arguments [(3, 4)] to every url
    """
    arg = [(3, 4)]
    assert add_arguments(url, arg) == expected_result


@pytest.mark.parametrize(('url', 'expected_result'), [
    ('http://example.com/foo.php', 'http://example.com/foo.php#3=4'),
    ('http://example.com/foo.php?1=2', 'http://example.com/foo.php?1=2#3=4'),
    ])
def test_add_fragment(url, expected_result):
    """
    Add arguments [(3, 4)] to every hash fragment of the URL
    """
    arg = [(3, 4)]
    assert add_fragment(url, arg) == expected_result


@pytest.mark.parametrize(('url', 'is_valid'), [
    ('http://example.com/foo.php', True),
    ('https://example.com/foo.php', True),
    ('ftp://example.com/foo.php', False),
    ('example.com/foo.php', False),
])
def test_check_url(url, is_valid):
    """
    Check every URL for validity
    """
    if is_valid:
        check_url(url)
    else:
        with pytest.raises(OauthistValidationError):
            check_url(url)
