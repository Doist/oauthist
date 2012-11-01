# -*- coding: utf-8 -*-
import redis as redis
from oauthist import orm
from oauthist.errors import OauthistValidationError
from oauthist.validators import check_url
from oauthist.utils import add_arguments

CLIENT_ID_LENGTH = 16
CLIENT_SECRET_LENGTH = 64

CLIENT_TYPES = ('web', 'user-agent', 'native')
CONFIDENTIAL_CLIENTS = ('web', )
PUBLIC_CLIENTS = ('user-agent', 'native')


# we don't use threading.local() as the only object which can suddenly
# change its state due to multiprocessing issues in the redis.Redis client
# But the official documentation ensures that redis.Redis() instances
# are thread-safe.
class Framework(object):
    pass

framework = Framework()


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


    id_length = CLIENT_ID_LENGTH
    # we don't want to add the attribute for redirect_urls and client_secret
    objects = orm.TaggedAttrsModelManager(['redirect_urls', 'client_secret', ])

    def validate(self):
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


class CodeRequest(orm.Model):

    @classmethod
    def from_werkzeug(cls, request):
        """
        Create CodeRequest object from Wekzeug/Flask request object

        Can raise OauthistValidationError 'invalid_response_type' if
        response_type GET argument is not equal to "code".
        """
        response_type = request.args.get('response_type')
        client_id = request.args.get('client_id')
        redirect_uri = request.args.get('redirect_uri')
        scope = request.args.get('scope')
        state = request.args.get('state')
        return cls(response_type=response_type, client_id=client_id,
                   redirect_uri=redirect_uri, scope=scope, state=state)

    def __init__(self, _id=None, **attrs):
        # if response_type is unset, then assume it is equal to "code", as
        # specification requires
        response_type = attrs.pop('response_type', 'code')
        expire = attrs.pop('expire', framework.authorization_code_timeout)
        accepted = attrs.pop('accepted', False)
        super(CodeRequest, self).__init__(_id=_id, expire=expire,
                                          response_type=response_type,
                                          accepted=accepted,
                                          **attrs)
        self.error = None
        # self.client is defined on check_broken invocation
        self.client = None

    def is_broken(self):
        """
        Return False if it doesn't make any sense to check the request further

        If `self.is_broken()` is True, then server must stop handling the request
        and show the error page.
        """
        try:
            self.check_broken()
        except OauthistValidationError as e:
            self.error = str(e)
            return True
        else:
            return False

    def check_broken(self):
        response_type = self.attrs.get('response_type')
        if not response_type:
            raise OauthistValidationError('missing_response_type')
        if response_type != 'code':
            raise OauthistValidationError('invalid_response_type')
        client_id = self.attrs.get('client_id')
        if not client_id:
            raise OauthistValidationError('missing_client_id')
        self.client = Client.objects.get(client_id)
        if not self.client:
            raise OauthistValidationError('invalid_client_id')
        redirect_uri = self.client.check_redirect_uri(self.attrs.get('redirect_uri'))
        self.attrs['redirect_uri'] = redirect_uri

    def is_invalid(self):
        try:
            self.check_invalid()
        except OauthistValidationError as e:
            self.error = str(e)
            return True
        else:
            return False

    def check_invalid(self):
        if self.error:
            raise OauthistValidationError(self.error)
        if not framework.scopes:
            return
        scopes = (self.attrs.get('scope') or '').strip().split()
        if not scopes:
            raise OauthistValidationError('missing_scope')
        if not set(scopes).issubset(set(framework.scopes)):
            raise OauthistValidationError('invalid_scope')

    def get_redirect(self, error=None):
        # just in case, check for broken client once again
        # and die with an exception if somebody forgot to execute
        # is_broken()
        self.check_broken()
        # if there is an error attribute or error, passed as option, return
        # error redirect
        if self.is_invalid() or error:
            return self.get_error_redirect(self.error or error)
        else:
            return self.get_success_redirect()

    def get_error_redirect(self, error):
        base_url = self.attrs['redirect_uri']
        state = self.attrs.get('state')
        args = [('error', error), ]
        if state:
            args.append(('state', state), )
        return add_arguments(base_url, args)

    def get_success_redirect(self):
        base_url = self.attrs['redirect_uri']
        state = self.attrs.get('state')
        if not self._id:
            raise ValueError('Code request object is unsaved')
        args = [('code', self._id), ]
        if state:
            args.append(('state', state), )
        return add_arguments(base_url, args)


    def accept(self):
        self.set(accepted=True)

    def decline(self, reason='access_denied'):
        self.error = reason
        self.delete()


#--- utility functions

def full_cleanup():
    """
    Cleanup the Redis database completely
    """
    Client.objects.full_cleanup()
    CodeRequest.objects.full_cleanup()
