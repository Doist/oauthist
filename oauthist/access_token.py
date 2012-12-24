# -*- coding: utf-8 -*-
import json
import ormist
from oauthist.core import framework
from oauthist.client import Client
from oauthist.authorization_code import Code
from oauthist.errors import OauthistValidationError, OauthistRuntimeError, InvalidAccessToken

JSON_HEADERS =  {
    'Content-Type': 'application/json;charset=UTF-8',
    'Cache-Control': 'no-store',
    'Pragma': 'no-cache',
}

class CodeExchangeRequest(object):
    """
    Request object aiming to exchange authorization code to access token.

    Transient object,  a it's a quite thin wrapper around HTTP request object,
    which primary goal is to validate passed arguments (we expect the
    authorization code id) and issue an access token.
    """

    @classmethod
    def from_werkzeug(cls, request):
        """
        Create CodeExchangeRequest instance from Werkzeug/Flask request

        :rtype CodeExchangeRequest:
        """
        arg_names = ('code', 'client_id', 'client_secret', 'redirect_uri',
                     'state', 'grant_type')
        kwargs = {}
        for arg_name in arg_names:
            kwargs[arg_name] = request.form.get(arg_name)

        return cls(**kwargs)


    def __init__(self, code=None, client_id=None, client_secret=None,
                 redirect_uri=None, state=None, expire=None,
                 grant_type='authorization_code'):
        """
        Constructor for code exchange request.

        :param code: authorization code, obtained by the client with help of
                     user
        :type code: str
        :param client_id: client id
        :type client_id: str
        :param client_secret: client secret, shared between server and client
                              only
        :type client_secret: str
        :param redirect_uri: if while obtaining authorization code, client
                             created a request with redirect uri, then this
                             redirect uri must be passed here.
                             Otherwise this field must be set to None
        :type redirect_uri: str
        :param state: if while obtaining authorization code, client issued a
                      random "state" parameter, then it should be passed here.
                      Otherwise this field myst be set to None
        :type state: str
        :expire: if you want to override default expiration timeout, defined in
                 the framework, you can pass the value here. Value may be
                 integer (seconds since now), timedelta or absulute datetime.
                 ``None`` means "use ``framework.access_token_timeout``".
        :type expire: int or datetime.timedelta or datetime.datetime
        """
        self.code = code
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.state = state
        self.grant_type = grant_type
        self.expire = expire or framework.access_token_timeout

        self.client_obj = Client.objects.get(self.client_id, system=framework.ormist_system)
        self.code_obj = Code.objects.get(self.code, system=framework.ormist_system)
        self.error = None
        self.error_description = None
        self.access_token = None

    def is_invalid(self):
        """
        Return True, if access token request is invalid
        """
        try:
            self.check_invalid()
        except OauthistValidationError as e:
            self.error = str(e)
            return True
        else:
            return False

    def check_invalid(self):
        if self.grant_type != 'authorization_code':
            raise OauthistValidationError('invalid_request')
        # check for missing values
        if not self.code:
            raise OauthistValidationError('invalid_request')
        if not self.client_id:
            raise OauthistValidationError('invalid_request')
        if not self.client_secret:
            raise OauthistValidationError('invalid_request')
        # check for missing objects
        if not self.client_obj:
            raise OauthistValidationError('invalid_client')
        if not self.code_obj:
            raise OauthistValidationError('invalid_grant')
        # check for invalid parameters
        self.redirect_uri = self.client_obj.check_redirect_uri(self.redirect_uri)
        if self.client_secret != self.client_obj.client_secret:
            raise OauthistValidationError('invalid_client')
        if self.state != self.code_obj.state:
            raise OauthistValidationError('invalid_grant')
        if self.redirect_uri != self.code_obj.redirect_uri:
            raise OauthistValidationError('invalid_grant')
        if not self.code_obj.attrs.get('accepted'):
            raise OauthistValidationError('invalid_grant')

    def exchange_for_token(self, **attrs):
        """
        Perform action "exchange code request for access token".

        During this procedure a new access token is created and returned and
        the code object is destroyed, therefore it's impossible to exchange
        the same authentication code for token twice or more.

        :rtype: AccessToken
        """
        self.check_invalid()
        if not self.access_token:
            self.access_token = AccessToken()
        # we have to copy all attributes from the code obj, except
        # those which we don't need anymore
        code_attrs = self.code_obj.attrs.copy()
        for key in ('state', 'accepted', 'redirect_uri', 'expire'):
            code_attrs.pop(key, None)
        code_attrs.update(attrs)
        self.access_token.set(**code_attrs)
        self.access_token.set_expire(self.expire)
        self.code_obj.delete()  # delete authorization code
        self.code_obj = None
        self.access_token.save(system=framework.ormist_system)
        return self.access_token

    def get_error(self):
        """
        Create and return AccessTokenError instance to pass to client via HTTP

        :rtype AccessTokenError:
        """
        if not self.error:
            raise OauthistRuntimeError('Error attribute is not defined, maybe '
                                       'you forgot to call '
                                       'CodeExchangeRequest.is_invalid()')
        return AccessTokenError(self.error)


class AccessToken(ormist.TaggedAttrsModel):
    """
    Access token object.

    Persistent object, used to manage clients' access to users' resources.

    Usually you shouldn't create instances of :class:`AccessToken` directly,
    using other methods instread.

    For example, to create access token from code request, use
    :meth:`CodeRequest.exchange_for_token`.

    Access token may have limited lifetime, but by default they're "eternal".
    You can change the lifetime value with :func:`oauthist.configure`
    """

    id_length = 64

    def to_werkzeug_response(self):
        """
        Return Werkzeug/Flask response object to pass access token via HTTP
        to client the most rightful way
        """
        from werkzeug.wrappers import Response
        content = self.get_json_content()
        return Response(json.dumps(content), headers=self.get_headers())

    def get_json_content(self):
        """
        Return JSON content of the access token, as defined in :rfc:`6749#4.3.3`
        """
        ret = {
            'access_token': self._id,
            'token_type': 'bearer',
            'scope': self.scope,
        }
        expires_in = self.ttl()
        if expires_in is not None:
            ret['expires_in'] = expires_in
        return ret

    def get_headers(self):
        """
        Return the dict with headers, according to :rfc:`6749#4.3.3`
        (define content-type, prevent caching)
        """
        return JSON_HEADERS


class AccessTokenError(object):
    """
    Object representing error while issuing access token

    Transient object, which is used to correctly form HTTP response with
    error message
    """

    def __init__(self, error):
        self.error = error

    def to_werkzeug_response(self):
        """
        Return Werkzeug/Flask response object to pass access token via HTTP
        to client the most rightful way
        """
        from werkzeug.wrappers import Response
        content = self.get_json_content()
        return Response(json.dumps(content), headers=self.get_headers(),
                        status=400)

    def get_json_content(self):
        """
        Return JSON content of the access token, as defined in :rfc:`6749#4.3.3`
        """
        return {
            'error': self.error,
        }


    def get_headers(self):
        """
        Return the dict with headers, according to :rfc:`6749#4.3.3`
        (define content-type, prevent caching)
        """
        return JSON_HEADERS



def verify_access_token(access_token, *scopes):
    """
    Check if access token is valid to get access to following list of scopes

    If list of scopes is empty, then check if access token is valid at all
    (can be used when the application doesn't use the concept of scopes).

    :param access_token: access token string
    :type access_token: str
    :param \*scopes: list of scopes, which token must be valid for. Note that
                     here the "OR"-logic is used. If one or more scope is
                     defined, then the token must be valid for at least one
                     scope in the list
    :return: AccessToken instance
    :rtype: AccessToken
    :raise: InvalidAccessToken
    """
    token_object = AccessToken.objects.get(access_token,
                                           system=framework.ormist_system)
    if not token_object:
        raise InvalidAccessToken()
    if not scopes:
        return token_object
    token_scopes = set(token_object.scope.split())
    required_scopes = set(scopes)
    if required_scopes.intersection(token_scopes):
        return token_object
    raise InvalidAccessToken()


def access_token_from_werkzeug(request):
    """
    Get access token string from Werkzeug request

    According to specification, access token can be found in:

    - authorization request header
    - request body (urlencoded)
    - request URI (as GET parameter)

    Access token can be extracted from either of these sources, but if token will
    be found more than in one resource, then, according to specification, server
    return None, as if no access token is found.

    :param request: Werkzeug request
    :return: request token as a string or None
    :rtype: str
    """
    header_token = request.headers.get('Authorization')
    if header_token:
        # check for header token, if defined
        header_token_chunks = header_token.split(' ', 1)
        if len(header_token_chunks) != 2:
            return None
        if header_token_chunks[0] != 'Bearer':
            return None
        header_token = header_token_chunks[1]

    form_token = request.form.get('access_token')
    args_token = request.args.get('access_token')

    active_token = None
    for token in (header_token, form_token, args_token):
        if token:
            if active_token:  # more than one token defined
                return None
            else:
                active_token = token

    return active_token
