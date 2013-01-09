# -*- coding: utf-8 -*-
import json
from oauthist import CONFIDENTIAL_CLIENTS
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


class GenericAccessTokenRequest(object):
    """
    Generic class to contain common code for different types of AccessToken
    requests. Represents transient objects.

    You shouldn't use this object directly, use their descendants,
    :class:`CodeExchangeRequest` and :class:`PasswordExchangeRequest` instead.
    """

    def is_invalid(self):
        """
        Return True if request is invalid. Leverages :meth:`check_invalid`
        """
        try:
            self.check_invalid()
        except OauthistValidationError as e:
            self.error = str(e)
            return True
        else:
            return False

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


class CodeExchangeRequest(GenericAccessTokenRequest):
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

        :param code: authorization code, obtained by the client with help of user
        :type code: str

        :param client_id: client id
        :type client_id: str

        :param client_secret: client secret, shared between server and client
        :type client_secret: str

        :param redirect_uri: if while obtaining authorization code, client
        created a request with redirect uri, then this redirect uri must be
        passed here. Otherwise this field must be set to None
        :type redirect_uri: str

        :param state: if while obtaining authorization code, client issued a
        random "state" parameter, then it should be passed here. Otherwise this
        field must be set to None
        :type state: str

        :param expire: if you want to override default expiration timeout,
        defined in the framework, you can pass the value here. Value may be
        integer (seconds since now), timedelta or absulute datetime. ``None``
        means "use ``framework.access_token_timeout``".
        :type expire: int or datetime.timedelta or datetime.datetime
        """
        self.code = code
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.state = state
        self.grant_type = grant_type
        self.expire = expire or framework.access_token_timeout

        self.client_obj = Client.objects.get(self.client_id)
        self.code_obj = Code.objects.get(self.code)
        self.error = None
        self.error_description = None
        self.access_token = None

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
        self.access_token.save()
        return self.access_token


class PasswordExchangeRequest(GenericAccessTokenRequest):
    """
    Request to exchange user requisites to access key.

    Transient object which accepts HTTP request parameters and a callback to
    verify requisites, and return AccessToken or AccessTokenError.

    Implement Resource Owner Password Credentials Grant flow (see :rfc:`6749#4.3`)
    """


    @classmethod
    def from_werkzeug(cls, request, verify_requisites, client_required=True,
                      client_secret_required=True):
        """
        Create PasswordExchangeRequest instance from Werkzeug/Flask request

        :param request: Werkzeug request object

        :param verify_requisites: callable which will be used to verify username
        and password, provided by the client. Must return dict to be associated
        with request object, or None, if requisites are invalid

        :param client_required: boolean flag, which is set to true, if client_id
        and client_secret are required. In principle, password authentication
        specification doesn't prevent "anonymous" requests for access token.
        With this option you may enforce client authentication.

        :param client_secret_required: by default "public clients" (user-agent
        and native) don't have client secret. Nonetheless, according to
        :rfc:`6749`, there is no explicit limitation to these types of clients.
        With his option you may make all clients use their client secrets

        :rtype PasswordExchangeRequest:
        """
        arg_names = ('username', 'password', 'scope', 'client_id',
                     'client_secret', 'grant_type')
        kwargs = {'verify_requisites': verify_requisites,
                  'client_required': client_required,
                  'client_secret_required': client_secret_required}
        for arg_name in arg_names:
            kwargs[arg_name] = request.form.get(arg_name)

        return cls(**kwargs)


    def __init__(self, username=None, password=None, scope=None, client_id=None,
                 client_secret=None, grant_type='password',
                 expire=None, verify_requisites=None, client_required=True,
                 client_secret_required=True):
        """
        Constructor for password exchange request.

        :param username: username, or another identifier of the user (user id or email)
        :type username: str

        :param password: user password
        :type password: string

        :param scope: space separated list of scopes
        :type scope: string

        :param client_id: client id
        :type client_id: str

        :param client_secret: client secret, shared between server and client
        :type client_secret: str

        :param expire: if you want to override default expiration timeout,
        defined in the framework, you can pass the value here. Value may be
        integer (seconds since now), timedelta or absulute datetime. ``None``
        means "use ``framework.access_token_timeout``" .
        :type expire: int or datetime.timedelta or datetime.datetime

        :param verify_requisites: callable which will be used to verify username
        and password, provided by the client. Must return dict to be associated
        with request object, or None, if requisites are invalid

        :param client_required: boolean flag, which is set to true, if client_id
        and client_secret are required. In principle, password authentication
        specification doesn't prevent "anonymous" requests for access token.
        With this option you may enforce client authentication.

        :param client_secret_required: by default "public clients" (user-agent
        and native) don't have client secret. Nonetheless, according to
        :rfc:`6749`, there is no explicit limitation to these types of clients.
        With his option you may make all clients use their client secrets
        """
        self.username = username
        self.password = password
        self.scope = scope
        self.client_id = client_id
        self.client_secret = client_secret
        self.grant_type = grant_type
        self.expire = expire or framework.access_token_timeout
        self.verify_requisites = verify_requisites
        self.client_required = client_required
        self.client_secret_required = client_secret_required

        self.client_obj = Client.objects.get(self.client_id)
        self.error = None
        self.error_description = None
        self.access_token = None
        self.user_attrs = None


    def check_invalid(self):
        if self.grant_type != 'password':
            raise OauthistValidationError('invalid_request')
        # check for missing values
        if not self.username:
            raise OauthistValidationError('invalid_request')
        if not self.password:
            raise OauthistValidationError('invalid_request')

        # check for missing object
        if self.client_required and not self.client_obj:
            raise OauthistValidationError('invalid_client')

        # check for client authentication
        if self.client_obj:
            client_secret_match = self.client_secret and self.client_obj.client_secret == self.client_secret
            if not client_secret_match:
                if self.client_secret_required:
                    raise OauthistValidationError('invalid_client')
                if self.client_obj.client_type in CONFIDENTIAL_CLIENTS:
                    raise OauthistValidationError('invalid_client')

        # check for user requisites
        self.user_attrs = self.verify_requisites(self.username, self.password)
        if self.user_attrs is None:  # invalid requisites
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
        token_attrs = dict(client_id=self.client_id, username=self.username,
                           scope=self.scope)
        token_attrs.update(**self.user_attrs)
        token_attrs.update(**attrs)
        self.access_token.set(**token_attrs)
        self.access_token.set_expire(self.expire)
        self.access_token.save()
        return self.access_token


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
            'access_token': self.id,
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



class ProtectedResourceRequest(object):
    """
    Protected resource request

    Transient objects which should be used to check whether client has access
    to user's protected resource.
    """
    def __init__(self, access_token):
        self.access_token = access_token


    @classmethod
    def from_werkzeug(cls, request):
        """
        Get access to token string from Werkzeug/Flask request

        According to specification, access token can be found in:

        - authorization request header
        - request body (urlencoded)
        - request URI (as GET parameter)

        Access token can be extracted from either of these sources, but if token will
        be found more than in one resource, then, according to specification, server
        return None, as if no access token is found.

        :param request: Werkzeug request
        :return: request token as a string or None
        :rtype: ProtectedResourceRequest
        """
        header_token = request.headers.get('Authorization')
        if header_token:
            # check for header token, if defined
            header_token_chunks = header_token.split(' ', 1)
            if len(header_token_chunks) != 2:
                return cls(None)
            if header_token_chunks[0] != 'Bearer':
                return cls(None)
            header_token = header_token_chunks[1]

        form_token = request.form.get('access_token')
        args_token = request.args.get('access_token')

        active_token = None
        for token in (header_token, form_token, args_token):
            if token:
                if active_token:  # more than one token defined
                    return cls(None)
                else:
                    active_token = token

        return cls(active_token)


    def verify_access_token(self, *scopes):
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
        token_object = AccessToken.objects.get(self.access_token)
        if not token_object:
            raise InvalidAccessToken()
        if not scopes:
            return token_object
        token_scopes = set(token_object.scope.split())
        required_scopes = set(scopes)
        if required_scopes.intersection(token_scopes):
            return token_object
        raise InvalidAccessToken()
