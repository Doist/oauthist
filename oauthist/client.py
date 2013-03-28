# -*- coding: utf-8 -*-
import ormist
from oauthist.utils import check_url
from oauthist.errors import OauthistValidationError
from oauthist.core import CLIENT_ID_LENGTH, CLIENT_TYPES, CONFIDENTIAL_CLIENTS, CLIENT_SECRET_LENGTH
from oauthist.compat import text, binary


class Client(ormist.TaggedAttrsModel):
    """
    A client object.

    Persistent object, storing all the information related to a registered client:

    :param client_secret: client secret. Random ASCII string used as client
    secret. Will be automatically generated and saved in database, unless
    explicitly defined.

    :param redirect_urls: List of redirect URLs. Should be passed as
    a list of strings. Will be converted to list of strings and
    stored in database.

    :param name: client name (string, optional)
    :param description: client description (string, probably multiline, optional)
    :param logo_url: client logo URL (string with URL, no extra requirements)
    :param owner_id: the identifier of the client owner.
    Depending on your system, may be a string or an integer

    Once a new client is registered, its client_id will be the `id` attribute

    This is how, for example, a new client with a link to actual user in your
    database can be saved.

    .. code-block:: python

        >>> client = Client.objects.create(redirect_urls=['http://example.com/oauth_callback'],
                                           name='A test client'
                                           owner_id=1234)

    Then you can get the list of all clients for a given user.

    .. code-block:: python

        >>> clients = Client.objects.filter(owner_id=123)
    """
    #: length of random string when a client_id will be generated.
    #: used by ormist underlying framework.
    id_length = CLIENT_ID_LENGTH

    # we don't want to add the attribute for redirect_urls, client_secret and
    # client_description
    objects = ormist.TaggedAttrsModelManager(['redirect_urls', 'client_secret',
                                              'client_description'])

    def validate(self):
        """
        Method which is called every time before the instance is saved.

        :raise: OauthistValidationError if data seem inconsistent.
        """
        # check for redirect URL
        redirect_urls  = self.attrs.get('redirect_urls')
        if not redirect_urls:
            raise OauthistValidationError('redirect_urls is not set')
        for url in redirect_urls:
            check_url(url)
        self.attrs['redirect_urls'] = redirect_urls


    def check_redirect_uri(self, redirect_uri):
        """
        Check redirect uri, passed from the client side, for correctness

        Used by :class:`CodeRequest` and other class to validate and normalize
        the redirect URI, provided by client.

        Check, whether it matches the contents of the database. If the match
        is found, then return the uri, otherwise raise invalid_redirect_uri exception

        :param redirect_uri: string with redirect URI
        :return: validated redirect URL
        :raise: OauthistValidationError if redirect URI is missing or invalid
        """
        if not redirect_uri:
            raise OauthistValidationError('missing_redirect_uri')

        if redirect_uri not in self.redirect_urls:
            raise OauthistValidationError('invalid_redirect_uri')
        return redirect_uri

