# -*- coding: utf-8 -*-
import ormist
from oauthist.errors import OauthistValidationError, OauthistRuntimeError
from oauthist.client import Client
from oauthist.core import framework
from oauthist.utils import add_arguments


class CodeRequest(object):
    """
    A code request object.

    Transient object, actually a thin wrapper around HTTP request, which only
    goal is to extract data from request, validate them, and if everything is
    good create a persistent :class:`Code` instance, save it to the database
    and return to a client in HTTP response.

    Code request has two methods to guide you to the right direction.

    - :meth:`CodeRequest.is_broken` shows that the request is completely
       broken and the most appropriate action here is just to display
       HTML page with error code
    - :meth:`CodeRequest.is_invalid` means that the request is invalid, but
      it's safe to stick to OAuth2 flow and return user back to the URL defined
      in the request to notify the application-initiator about the problem.

    Code requests have limited lifetime (3600 seconds by default). You can change
    this value with :func:`oauthist.configure`
    """

    @classmethod
    def from_werkzeug(cls, request):
        """
        Create CodeRequest object from Werkzeug/Flask request object

        :rtype CodeRequest:
        """
        response_type = request.args.get('response_type')
        client_id = request.args.get('client_id')
        redirect_uri = request.args.get('redirect_uri')
        scope = request.args.get('scope')
        state = request.args.get('state')
        return cls(response_type=response_type, client_id=client_id,
                   redirect_uri=redirect_uri, scope=scope, state=state)


    def __init__(self, response_type='code', client_id=None, redirect_uri=None,
                 scope=None, state=None, expire=None):
        """
        Create code request object

        Instantiate object from your HTTP request

        :param response_type: response type string (from GET options). Must be "code"
        :param client_id: string with client id (from GET options)
        :param redirect_uri: callback redirect URI (from GET options). Can
                             be None, if there is only one URL is defined
                             in client model, otherwise should match one of
                             urls, defined there
        :param scope: space separated list of scopes
        :param state: optional, yet recommended random value, provided by the
                      client in its GET request. If provided, server code
                      must return it back with the response.
        :param expire: expiration timeout (in seconds, timedelta or datetime
                       object). Constant, defined by server developer, if not
                       set, default value is used
        """
        self.response_type = response_type
        self.client_id = client_id
        self.client = Client.objects.get(client_id, system=framework.ormist_system)
        self.redirect_uri = redirect_uri
        self.expire = expire or framework.authorization_code_timeout
        self.scope = scope
        self.state = state

        # self.error is defined in is_broken() and is_invalid() methods
        self.error = None
        # self.code is defined on save_code method
        self.code = None

    def is_broken(self):
        """
        Return True if it doesn't make any sense to check the request further

        If :meth:`self.is_broken` is True, then server must stop handling the request
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
        if not self.response_type:
            raise OauthistValidationError('missing_response_type')
        if self.response_type != 'code':
            raise OauthistValidationError('invalid_response_type')
        if not self.client_id:
            raise OauthistValidationError('missing_client_id')
        if not self.client:
            raise OauthistValidationError('invalid_client_id')
        self.redirect_uri = self.client.check_redirect_uri(self.redirect_uri)

    def is_invalid(self):
        """
        Return True, if code request is invalid, but it is safe to redirect user back

        Currently checks for scopes list validity
        """
        # ensure nobody's forgotten to check for broken request
        self.check_broken()
        try:
            self.check_invalid()
        except OauthistValidationError as e:
            self.error = str(e)
            return True
        else:
            return False

    def check_invalid(self):
        """
        Helper function which raises OauthistValidationError if request is invalid
        """
        if self.error:
            raise OauthistValidationError(self.error)
        if not framework.scopes:
            return
        scope_list = (self.scope or '').strip().split()
        if not scope_list:
            raise OauthistValidationError('missing_scope')
        if not set(scope_list).issubset(set(framework.scopes)):
            raise OauthistValidationError('invalid_scope')

    def get_redirect(self, error=None):
        """
        Return redirect, as described in :rfc:`6749#4.1.2`

        If there is an code object, then proxy method invocation there.

        In no code defined (because request is invalid and you want to respond
        immediately), then return error response by itself

        :param error: string with error
        :return: string containing fully composed absolute URL which user
                 should be redirected to
        """
        error = error or self.error
        if self.code:
            return self.code.get_redirect(error=error)
        if not error:
            raise OauthistRuntimeError('No error defined, and no code saved. What'
                                       'redirect do you want to return?')
        args = [('error', error), ]
        if self.state:
            args.append(('state', self.state), )
        return add_arguments(self.redirect_uri, args)


    def save_code(self, **attrs):
        """
        If eveything is okay, then create and return a new :class:`Code` instance

        If request contains errors (and they weren't checked by
        :func:`is_broken` and :func:`is_invalid`), raise
        :class:`OauthistValidationError`

        :param attrs: additional set of attributes, which should be bound to
                      the :class:`Code` instance, so that later we can identify
                      its owner or other properties somehow.
        """
        self.check_broken()
        self.check_invalid()
        if not self.code:
            self.code = Code()
        self.code.set(client_id=self.client_id, redirect_uri=self.redirect_uri,
                      scope=self.scope, state=self.state)
        self.code.set(**attrs)
        self.code.set_expire(self.expire)
        self.code.save(system=framework.ormist_system)
        return self.code


class Code(ormist.Model):
    """
    Authorization code as defined in :rfc:`6749#1.3.1`

    Persistent object, which is stored in database and returned to client via
    HTTP. You probably should never create this object directly, but should use
    :meth:`CodeRequest.save_code(...)` instead.

    Saved with `save_code` object has at least following attributes. You can
    pass more data to it, if you wish.

    - :data:`client_id`: id of client, requested for the access
    - :data:`redirect_uri`: redirect URI, passed in the HTTP request
    - :data:`scope`: space separated list of scopes which this code is valid for.
    - :data:`state`: random value, passed from client
    """

    def get_redirect(self, error=None):
        """
        Return URL to redirect client to

        :param error: error message
        :return: string with redirect
        """
        if error:
            return self.get_error_redirect(error=error)
        else:
            return self.get_success_redirect()

    def accept(self):
        """
        Accept code and return redirect URL

        Behind the scenes, the `accepted=True` is stored as the value of the
        instance attribute.

        If everything is okay, return success redirect with the code
        """
        self.set(accepted=True)
        self.save(system=framework.ormist_system)
        return self.get_success_redirect()

    def get_success_redirect(self):
        """
        :return: string with URL where the client should be redirected to
        """
        redirect_uri = self.attrs['redirect_uri']
        state = self.attrs.get('state')

        args = [('code', self._id), ]
        if state:
            args.append(('state', state), )

        return add_arguments(redirect_uri, args)

    def decline(self, error='access_denied'):
        """
        Decline code request and return corresponding callback URL

        Behind the scenes it removes the object completely from the Redis.

        :attr error: you may pass it to the function to denote that the
                     request is rejected by user. Usually, the most used
                     argument here will be the "access_denied" value.

        :return: redirect URL where client should be redirected to
        """
        self.delete()
        return self.get_error_redirect(error=error)

    def get_error_redirect(self, error='access_denied'):
        """
        Construct and return URL with error message.

        :param error: error message to return
        :return: complete error URL, containing among others correct state
                 parameter.
        """
        redirect_uri = self.attrs['redirect_uri']
        state = self.attrs.get('state')
        args = [('error', error), ]
        if state:
            args.append(('state', state), )
        return add_arguments(redirect_uri, args)
