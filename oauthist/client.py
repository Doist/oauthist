# -*- coding: utf-8 -*-
import ormist
from oauthist.utils import check_url
from oauthist.errors import OauthistValidationError
from oauthist.core import CLIENT_ID_LENGTH, CLIENT_TYPES, CONFIDENTIAL_CLIENTS, CLIENT_SECRET_LENGTH
from oauthist.compat import text, binary


class Client(ormist.TaggedAttrsModel):

    id_length = CLIENT_ID_LENGTH
    # we don't want to add the attribute for redirect_urls and client_secret
    objects = ormist.TaggedAttrsModelManager(['redirect_urls', 'client_secret', ])

    def validate(self):
        # check client type
        client_type = self.attrs.get('client_type')
        if client_type not in CLIENT_TYPES:
            raise OauthistValidationError('%r is not a valid client type' % client_type)
            # check for redirect URL
        redirect_urls  = self.attrs.get('redirect_urls')
        if not redirect_urls:
            raise OauthistValidationError('redirect_urls is not set')
        if isinstance(redirect_urls, (text, binary)):
            redirect_urls = [redirect_urls, ]
        for url in redirect_urls:
            check_url(url)
        self.attrs['redirect_urls'] = redirect_urls
        # check for client secret
        client_secret = self.attrs.get('client_secret')
        if not client_secret and client_type in CONFIDENTIAL_CLIENTS:
            client_secret = ormist.random_string(CLIENT_SECRET_LENGTH)
        self.attrs['client_secret'] = client_secret

    def check_redirect_uri(self, redirect_uri):
        """
        Check redirect uri for correctness

        Used by :class:`CodeRequest` and other class to validate and normalize
        the redirect URI, provided by client.

        Validation rules are following

        1. If redirect uri isn't provided, but there's only one in database
           return URI from database
        2. If redirect uri isn't provided, and there is more than on url
           in database, raise missing_redirect_uri exception
        3. If redirect uri is provided, then check, whether it matches the
           contents of the database. If the match is found, then return the
           uri, otherwise raise invalid_redirect_uri exception
        """
        if not redirect_uri:
            if len(self.redirect_urls) == 1:
                return self.redirect_urls[0]
            else:
                raise OauthistValidationError('missing_redirect_uri')

        if redirect_uri not in self.redirect_urls:
            raise OauthistValidationError('invalid_redirect_uri')
        return redirect_uri

