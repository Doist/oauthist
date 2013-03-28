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
#
# But the redis-py documentation ensures that redis.Redis() instances
# are thread-safe.
class framework(object):
    scopes = None
    authorization_code_timeout = None
    access_token_timeout = None
    ormist_system = 'default'


def configure(ormist_system='default',
              authorization_code_timeout=3600,
              access_token_timeout=None):

    """
    Configure oauthist framework

    :param ormist_system: name of the "system" (Redis database connection) which
     will be used to store OAuth 2.0 objects

    :param authorizarion_code_timeout: timeout for authorization codes (`Code`
    instances)

    :param access_code_timeout: expiration timeout of access token
    (`AccessToken` instances). By default ``None`` which means that token
    never expires unless explicitly revoked
    """
    framework.authorization_code_timeout = authorization_code_timeout
    framework.access_token_timeout = access_token_timeout
    framework.ormist_system = ormist_system
    from oauthist.client import Client
    from oauthist.authorization_code import Code
    from oauthist.access_token import AccessToken
    Client.objects.set_system(ormist_system)
    Code.objects.set_system(ormist_system)
    AccessToken.objects.set_system(ormist_system)


#--- utility functions

def full_cleanup():
    """
    Cleanup the Redis database completely
    """
    from oauthist.client import Client
    from oauthist.authorization_code import Code
    from oauthist.access_token import AccessToken
    Client.objects.full_cleanup()
    Code.objects.full_cleanup()
    AccessToken.objects.full_cleanup()
