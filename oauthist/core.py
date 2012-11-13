# -*- coding: utf-8 -*-
import redis
import ormist

CLIENT_ID_LENGTH = 16
CLIENT_SECRET_LENGTH = 64

CLIENT_TYPES = ('web', 'user-agent', 'native')
CONFIDENTIAL_CLIENTS = ('web', )
PUBLIC_CLIENTS = ('user-agent', 'native')


# we don't use threading.local() as the only object which can suddenly
# change its state due to multiprocessing issues in the redis.Redis client
# But the official documentation ensures that redis.Redis() instances
# are thread-safe.
class framework(object):
    redis = None
    prefix = None
    scopes = None
    authorization_code_timeout = None
    access_token_timeout = None


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
    ormist.configure(framework.redis, framework.prefix)


#--- utility functions

def full_cleanup():
    """
    Cleanup the Redis database completely
    """
    from oauthist.client import Client
    from oauthist.authorization_code import Code
    Client.objects.full_cleanup()
    Code.objects.full_cleanup()
