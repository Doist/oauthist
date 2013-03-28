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
                 scope=None, state=None):
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
        """
        self.response_type = response_type
        self.client_id = client_id
        self.client = Client.objects.get(client_id)
        self.redirect_uri = redirect_uri
        self.scope = scope
        self.state = state

        # self.error is defined in is_broken() and is_invalid() methods
        self.error = None
        # self.code is defined on save_code method
        self.code = None


    def is_broken(self, raise_exc=False):
        """
        Return True if it doesn't make any sense to check the request further

        If :meth:`self.is_broken` is True, then server must stop handling the request
        and show the error page.
        """
        try:
            self._check_broken()
        except OauthistValidationError as e:
            if raise_exc:
                raise
            return True
        else:
            return False

    def _check_broken(self):
        if not self.response_type:
            raise OauthistValidationError('missing_response_type')
        if self.response_type != 'code':
            raise OauthistValidationError('invalid_response_type')
        if not self.client_id:
            raise OauthistValidationError('missing_client_id')
        if not self.client:
            raise OauthistValidationError('invalid_client_id')
        self.redirect_uri = self.client.check_redirect_uri(self.redirect_uri)

    def get_error_redirect(self, error):
        """
        Return a HTTP redirect with error, as defined in :rfc:`6749#4.1.2.1`

        :param error: error code (see the list of possible strings in the specification)

        :return: a string with HTTP URL which can be used in Location header
        for redirect
        """
        args = [('error', error), ]
        if self.state:
            args.append(('state', self.state))
        return add_arguments(self.redirect_uri, args)


    def save_code(self, user_id):
        """
        If request is valid, create and return a new :class:`Code` instance

        If request contains errors (and they weren't checked by
        :func:`is_broken`), raise :class:`OauthistValidationError`

        :param user_id: the identifier of the user (a resource owner), usually
        should be set from request session by your own code.
        """
        self.is_broken(raise_exc=True)
        code = Code()
        code.set(client_id=self.client_id, redirect_uri=self.redirect_uri,
                 scope=self.scope, state=self.state, user_id=user_id)
        code.set_expire(framework.authorization_code_timeout)
        code.save()
        return code


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

    def accept(self):
        """
        Accept code and return redirect URL

        Behind the scenes, the `accepted=True` is stored as the value of the
        instance attribute.

        If everything is okay, return success redirect with the code
        """
        self.set(accepted=True)
        self.save()
        return self.get_success_redirect()

    def get_success_redirect(self):
        """
        :return: string with URL where the client should be redirected to
        """
        redirect_uri = self.attrs['redirect_uri']
        state = self.attrs.get('state')

        args = [('code', self.id)]
        if state:
            args.append(('state', state), )

        return add_arguments(redirect_uri, args)

    def decline(self):
        """
        Decline code request and return corresponding callback URL

        Behind the scenes it removes the object completely from the Redis.

        :return: redirect URL where client should be redirected to
        """
        self.accepted = False
        self.delete()
        return self.get_error_redirect()

    def get_error_redirect(self):
        """
        Construct and return URL with error message.

        :return: complete error URL, containing among others correct state
                 parameter and error code "access_denied"
        """
        redirect_uri = self.attrs['redirect_uri']
        state = self.attrs.get('state')
        args = [('error', 'access_denied'), ]
        if state:
            args.append(('state', state), )
        return add_arguments(redirect_uri, args)
