# -*- coding: utf-8 -*-
import redis
from oauthist.roles import Client
from oauthist.utils import RandomGenerator
from oauthist.validators import check_client_type, check_redirect_url, CONFIDENTIAL_CLIENTS


class Framework(object):

    CLIENT_ID_LENGTH = 16
    CLIENT_SECRET_LENGTH = 64

    def __init__(self, prefix=None, scopes=None, authorization_code_timeout=3600,
                 access_token_timeout=None, **redis_kwargs):
        self.configure(prefix=prefix,
                       scopes=scopes,
                       authorization_code_timeout=authorization_code_timeout,
                       access_token_timeout=access_token_timeout,
                       **redis_kwargs)
        self.rand = RandomGenerator(self.redis)

    def configure(self, prefix=None, scopes=None, authorization_code_timeout=3600,
                  access_token_timeout=None, **redis_kwargs):

        """
        Configure oauthist framework

        :param prefix: the string prefix to use to store and search for keys in
                       Redis database
        :param scopes: list of strings, defining allowed access token scopes. If
                       unset, any scopes accepted
        :param authorizarion_code_timeout:
        :param access_code_timeout: expiration timeout of access token
                                    (by default ``None`` which means that token
                                    never expires unless explicitly revoked)
        :param \*\*redis_kwargs: set of parameters to configure connection to Redis
                                 server
        """
        self.prefix = prefix
        self.scopes = scopes or []
        self.authorization_code_timeout = authorization_code_timeout
        self.access_token_timeout = access_token_timeout
        self.redis_kwargs = redis_kwargs
        self.redis = redis.Redis(**redis_kwargs)

    #--- client related functions

    def register_client(self, client_type, redirect_url, attrs=None):
        check_client_type(client_type)
        check_redirect_url(redirect_url)
        client_id = self.rand.insert_in_set('clients', self.CLIENT_ID_LENGTH)
        if client_type in CONFIDENTIAL_CLIENTS:
            client_secret = self.rand.string(self.CLIENT_SECRET_LENGTH)
        else:
            client_secret = None
        attrs = attrs or {}
        client = Client(self, client_id, client_type, redirect_url,
                        client_secret=client_secret, attrs=attrs)
        client.save()
        return client

    def get_client(self, client_id):
        """
        Return client by its id
        """
        return Client.from_db(self, client_id)

    #--- utility functions

    def full_cleanup(self):
        """
        Cleanup the Redis database completely
        """
        templates = ['clients', 'client:*']
        keys = []
        for tmpl in templates:
            keys.append(self.redis.keys(self._key(tmpl)))
        if keys:
            self.redis.delete(*keys)

    def _key(self, key, *args, **kwargs):
        if self.prefix:
            template = '{0}:{1}'.format(self.prefix, key)
        else:
            template = key
        if args or kwargs:
            template = template.format(*args, **kwargs)
        return template
