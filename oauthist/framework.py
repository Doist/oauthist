# -*- coding: utf-8 -*-
import threading
import redis as redis
from oauthist import orm
from oauthist.roles import Client
from oauthist.errors import OauthistValidationError
from oauthist.validators import check_url

CLIENT_ID_LENGTH = 16
CLIENT_SECRET_LENGTH = 64

CLIENT_TYPES = ('web', 'user-agent', 'native')
CONFIDENTIAL_CLIENTS = ('web', )
PUBLIC_CLIENTS = ('user-agent', 'native')


framework = threading.local()


def configure(redis_client=None, prefix=None, scopes=None, authorization_code_timeout=3600,
              access_token_timeout=None):

    """
    Configure oauthist framework

    :param redis_client: instance of :class:`redis.Redis` connection. If None,
                         a new redis connection with empty set of arguments
                         is created
    :param prefix: the string prefix to use to store and search for keys in
                   Redis database
    :param scopes: list of strings, defining allowed access token scopes. If
                   unset, any scopes accepted
    :param authorizarion_code_timeout:
    :param access_code_timeout: expiration timeout of access token
                                (by default ``None`` which means that token
                                never expires unless explicitly revoked)
    """
    framework.redis = redis_client or redis.Redis()
    framework.prefix = prefix
    framework.scopes = scopes
    framework.authorization_code_timeout = authorization_code_timeout
    framework.access_token_timeout = access_token_timeout
    orm.configure(framework.redis, framework.prefix)



class Client(orm.TaggedAttrsModel):
    _id_length = CLIENT_ID_LENGTH

    # we don't want to add the attribute for redirect_urls
    _exclude_attrs = ['redirect_urls', ]

    def save(self):
        # check client type
        client_type = self.attrs.get('client_type')
        if client_type not in CLIENT_TYPES:
            raise OauthistValidationError('%r is not a valid client type' % client_type)
        # check for redirect URL
        redirect_urls  = self.attrs.get('redirect_urls')
        if not redirect_urls:
            raise OauthistValidationError('redirect_urls is not set')
        if isinstance(redirect_urls, basestring):
            redirect_urls = [redirect_urls, ]
        for url in redirect_urls:
            check_url(url)
        self.attrs['redirect_urls'] = redirect_urls
        # check for client secret
        client_secret = self.attrs.get('client_secret')
        if not client_secret and client_type in CONFIDENTIAL_CLIENTS:
            client_secret = orm.random_string(CLIENT_SECRET_LENGTH)
        self.attrs['client_secret'] = client_secret
        super(Client, self).save()


#--- utility functions

def full_cleanup():
    """
    Cleanup the Redis database completely
    """
    Client.full_cleanup()
