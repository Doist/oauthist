.. _getting_started:

Getting started with oauthist
==============================

.. _gettings_started_installation:

Installation
------------

`oauthist` uses `Redis`_ as a storage.

.. code-block:: console

   $ sudo apt-get install redis-server

The client library is installed automatically as a dependency for current package

.. code-block:: console

   $ pip install oauthist

.. _Redis: http://redis.io


.. _getting_started_configuration:

Configuration
-------------

Use :func:`configure` function to set up the framework.

Function accepts following parameters:

- :option:`host`, :option:`port`, :option:`db`, etc (optional): set of parameters
  to configure connection to Redis server
- :option:`scopes` (optional): list of strings, defining allowed
  `access token scopes`_. If unset, any scopes accepted.
- :option:`authorization_code_timeout` (optional): expiration timeout of
  authorization code in seconds (by default, 3600).
- :option:`access_token_timeout` (optional): expiration timeout of access token
  (by default ``None`` which means that token never expires unless explicitly
  revoked)
- :option:`prefix` (recommended): the string prefix to use to store
  and search for keys in Redis database

Sample initialization:

.. code-block:: python

   >>> import oauthist
   >>> oauthist.configure(redis.Redis(), prefix='oauthist')

Code examples in manual suppose, that you have already the framework,
initialized as described.

.. _getting_started_creating_clients:

Creating clients
----------------

According to the specification, before starting to use API calls, every client
should be registered with the `client registration`_. From the point of view of
OAuth server, the only two arguments here are required:

- :option:`client_type`: the type of client, according to OAuth sepcification
  (can be either "web", "user-agent" or "native")
- :option:`redirect_urls`: list of redirection URL (strings).

.. note:: to prevent the "`Open Redirectors`_" type of attacks, all possible
          redirection URLs must be explicitly set up on the configuration step.

A new random client-id will be generated, and for client of "web" type a shared
secret will also be issued

.. code-block:: python

   >>> extra_kwargs = dict(user_id=1234, name='My Client', description='Hello world')
   >>> client = oauthist.Client(client_type='web',
                                redirect_urls=['http://example.com/oauth2cb'],
                                **extra_kwargs)
   >>> client.id
   'ORG8hSAuTEb762AO'
   >>> client.secret
   'cx2kQAPjtCKlUGvwQPYA6yZ22OXDTrV5SbrGafqzHzGXQcDIgsI5uyCaLI8emjGn'
   >>> client.name
   'My Client'

All arguments, passed as extra kwargs, must be strings or objects unambiguously
converted to strings, will be stored in the Redis, and can be accessed as
object attributes.

The good part of it is that you may filter clients by any of the extra
attributes, so that they can be considered also as tags:

.. code-block:: python

   >>> oauthist.Client(user_id=1234, ...).save()
   >>> oauthist.Client(user_id=1234, ...).save()
   >>> oauthist.Client.objects.find(user_id=1234)  # return two clients


.. _client registration: http://tools.ietf.org/html/rfc6749#section-2
.. _access token scopes: http://tools.ietf.org/html/rfc6749#section-3.3
.. _Open Redirectors: http://tools.ietf.org/html/rfc6749#section-10.15

.. _getting_started_authorization:

Issuing authorization codes and access tokens
---------------------------------------------

Issuing authorization code
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Web clients having the secret shared with the authorization server should use
two step authorization procedure.

1. With the help of user, they get the authorization code. This code is available both
   to user and to client, but it is completely useless for anybody who doesn't
   dispose the client secret.
2. They exchange the secret code to access token

Issuing a secret code basically means "creating correct redirect URI" with the
code in its GET argument.

To start working you should create the :class:`CodeRequest` object first.

.. code-block:: python

   >>> req = oauthist.CodeRequest(client_id='...',
   ...                             redirect_uri='http://...',
   ...                             scope='...',
   ...                             state='...')

If you use `Werkzeug`_ or the framework based on it, you may call

.. code-block:: python

   >>> req = oauthist.CodeRequest.from_werkzeug(request)


The procedure of issuing of the secret code works passes following steps.

1. Server ensures, that request hasn't been forged in any way. If the request
   is just broken, server stops normal processing of the request, and returns
   the page, containing the error message:

       If the request fails due to a missing, invalid, or mismatching
       redirection URI, or if the client identifier is missing or invalid,
       the authorization server SHOULD inform the resource owner of the
       error and MUST NOT automatically redirect the user-agent to the
       invalid redirection URI.

   Here we refers to this state of request as "broken" and have corresponding
   method of code request: :func:`code_request.is_broken`.

2. Server performs some more formal checks. Currently the only check which
   framework can do without any help from the application programmer is to
   check for validity of received set of scopes. If scopes are invalid, it is
   safe at this point to return redirect. We call this state of request
   "invalid" and have a method :func:`code_request.is_invalid` for this sort
   of checking.

3. If everything looks good from the point of view of the framework, the
   application programmer should create the code and ask user for permission
   to authorize it. It is important to not that although the code
   is saved, it doesn't mean at all that the code can be exchanged for access
   token. Usually you store the code request along with user id attached:

   .. code-block:: python

        code = code_request.save_code(user_id=USER_ID)


4. Then server displays the confirmation window to the user, and depending on
   user's answer the state of the code can change itself to "accepted" or to
   "declined". When code is accepted, a new property "accepted" is defined and
   set to True, when it is declined, the code is simply removed from the
   database.

   Usually handling of user input is provided in separate HTTP request.
   To mark request as accepted, you invoke :meth:`code.accept`,
   otherwise you run :meth:`code.decline`

That's how the request handling can be performed in to views of Flask
framework:

.. code-block:: python

    @app.route('/auth_endpt')
    def auth_endpt():
        code_req = CodeRequest.from_werkzeug(request)
        if code_req.is_broken():
            return render_template('server/auth_endpt_broken.html',
                                   error=code_req.error)
        if code_req.is_invalid():
            return redirect(code_req.get_redirect())

        # at this point we save the code request and wait for user confirmation
        code = code_req.save(user_id=USER_ID)
        return render_template('server/auth_endpt_confirmation.html', code=code,
                                client=code_req.client)


    @app.route('/auth_endpt/confirmation')
    def auth_endpt_confirmation():
        # get some information from the form
        code_id = ...  # it can be passed between handlers in a hidden for field
                           # or saved in session
        # search for code request
        code = Code.objects.get(code_id)
        if user_declined_access():
            return redirect(code.decline())
        else:
            return redirect(code.accept())

See `4.1.2.1 Error Response`_ section of RFC for more variants of `error`
argument of :func:`decline`.

.. _Werkzeug: http://werkzeug.pocoo.org/
.. _4.1.2.1 Error Response: http://tools.ietf.org/html/rfc6749#section-4.1.2.1


Exchanging authorization code for access token
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Once Client receives the authorization code, it immediately exchanges it for
access token.

.. note:: By default authorization code has limited lifetime, only one hour,
          whereas the access token by default is "eternal", yet revocable.

Create the code exchange request

.. code-block:: python

   req = oauthist.CodeExchangeRequest(client_id='...',
                                      client_secret='...',
                                      redirect_uri='...',
                                      code='...')

Similarly, if you're a lucky `Werkzeug`_ user, you can create the object
by its Request.

.. code-block:: python

    req = oauthist.CodeExchangeRequest.from_werkzeug(request)

Verify, is request is valid.

.. code-block:: python

    if req.is_invalid():
        return req.get_error().to_werkzeug_response()


Then do exchange it for access token

.. code-block:: python

   access_token = req.exchange_for_token()


According to the section `Issuing an Access Token`_ of the RFC 6749, response
must be encoded in JSON, and headers must contain correct ``Cache-Control`` and
``Pragma`` headers::

     HTTP/1.1 200 OK
     Content-Type: application/json;charset=UTF-8
     Cache-Control: no-store
     Pragma: no-cache

     {
       "access_token":"2YotnFZFEjr1zCsicMWpAA",
       "token_type":"example",
       "expires_in":3600,
       "refresh_token":"tGzv3JOkF0XG5Qx2TlKWIA",
       "example_parameter":"example_value"
     }

You can use corresponding methods of response object to convert it to HTTP
response of `Werkzeug`, or to get dict of headers and the body contents
to use them to build the response of your framework.

.. code-block:: python

   >>> resp.to_werkzeug_response()
   ...
   >>> resp.get_code()
   200
   >>> resp.get_headers()
   {'Content-Type': 'application/json;charset=UTF-8', ...}
   >>> resp.get_body()
   '{...}'


Refreshing access token
~~~~~~~~~~~~~~~~~~~~~~~

oauthist framework intentionally doesn't issue refresh tokens, as we strive to keep
things as simple as possible for us and for clients, and the security
benefits introducing with access codes seem questionable.

.. _Issuing an Access Token: http://tools.ietf.org/html/rfc6749#section-5

Implicit grant
~~~~~~~~~~~~~~

The implicit grant type is used to obtain access tokens with Client who can't
keep secrets (mostly client-side JavaScript applications). Instead of issuing
the code which then can be exchanged to access token, the server returns the
access token in the very first response.

The flow is similar to one used to obtain the code.

Create the :class:`AccessTokenRequest` object

.. code-block:: python

   >>> req = oauthist.AccessTokenRequest(client_id='...',
   ...                             redirect_uri='http://...',
   ...                             scope='...',
   ...                             state='...')

If you use `Werkzeug` or the framework based on it, you may call

.. code-block:: python

   >>> req = oauthist.AccessTokenRequest.from_werkzeug(request)

Check if the request is valid

.. code-block:: python

   >>> if not req.is_valid():
   ...     return render('error.html', error=req.error)


Do additional checks, get positive (or negative) answer from the User,
and return the HTTP response redirect with the access token.

.. code-block:: python

   >>> redirect_uri = req.get_redirect(user_id=user_id)
   >>> str(redirect_uri)
   'http://...#code=<...>&state=<...>'


If you need to return error

.. code-block:: python

   >>> redirect_uri = req.get_redirect(error='access_denied')
   >>> str(redirect_uri)
   'http://...#error=access_denied'

See `4.2.2.1 Error Response`_ section of RFC for more variants of error argument.

.. _4.2.2.1 Error Response: http://tools.ietf.org/html/rfc6749#section-4.2.2.1


Resource Owner Password Credentials Grant
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The resource owner password credentials grant type is suitable in cases where
the resource owner has a trust relationship with the client, such as the device
operating system or a highly privileged application.

Technically, this kind of grant is nothing more but a "shortcut" of the server
side flow, but here Client doesn't ask User to provide the code, and just sends
"bare" user's credentials (username and password) to Server instead.

To check whether username and password, provided by the client, are valid, you
should write a function.

- The function accepts two arguments: username and password
- Function must return `None`, if user not found, or user's password doesn't
  match the one provided by the client.
- Function must return dict (the dict may be empty), to denote that user is
  valid. The contents of the dict will be written to the access token, returned
  by the client.
- Function must be passed as an argument to :class:`PasswordExchangeRequest`
  constructor

Trivial hypothetical example

.. code-block:: python

    def verify_requisites(username, password):
        user = User.objects.get(username=username, password=password)
        if user is None:
            return None
        else:
            return {'user_id': user.id}

Create the code exchange request

.. code-block:: python

   req = oauthist.PasswordExchangeRequest(username='...',
                                          password='...',
                                          client_id='...',
                                          client_secret='...',
                                          scope='...',
                                          verify_requisites=verify_requisites)


Parameters `client_id` and `client_secret` are required for private client;
as `client_secret` doesn't exist for public client, there is nothing to pass
here; and finally, `client_id` for public client is optional.

Additionally, there are two optional boolean flags, altering the behavior of the
request object: `client_required` -- forbid "anonymous" clients, and
`client_secret_required` -- forbid public (in terms of OAuth specification)
clients.

Verification of the request and issuing of the code is provided the same way
as for :class:`CodeExchangeRequest`. Below is a Flask-based example

.. code-block:: python

    req = PasswordExchangeRequest.from_werkzeug(request, verify_requisites)
    if req.is_invalid():
        return req.get_error().to_werkzeug_response()
    else:
        access_token = req.exchange_for_token()
        return access_token.to_werkzeug_response()

.. _getting_started_verifying_requests:

Verifying requests with access tokens
--------------------------------------

The way access tokens should be used is defined in the `Access Tokens Types`_
chapter of RFC 6749.

The framework supports Bearer Tokens (see `RFC 6750`_). According to the
recommendation, the token can be passed in ``Authorization:`` HTTP header, in
POST or GET request as a parameter.

If you use Werkezeug-based framework, you may easily retrieve the token string
from any of these source

.. code-block:: python

   request = oauthist.ProtectedResourceRequest(http_request)

The function returns object with field :attr:`access_token`, which will be set
to `None` if token hasn't been found.

Once you received the bearer token string, you must check if it is valid to your
scope. If the token is valid, the :class:`AccessToken` object will be returned,
otherwise :class:`InvalidAccessToken` exception will be raised.

.. code-block:: python

   >>> token = oauthist.ProtectedResourceRequest(access_token_string).verify_access_token('scopeA', 'scopeA-B')

.. note:: The successful response will be returned, if token is valid **either**
          for 'scopeA' **or** 'scopeA-B'. If for some reasons you want to ensure
          that token is valid for **both** scopes, use cycle

          .. code-block:: python

             try:
                 for scope in scopes:
                    token = req.verify_access_token(scope)
             except oauthist.InvalidAccessToken as e:
                 # handle exception here
                 pass


**How to identify the user then?**

As you may remember, when you save a :class:`Code` (Authorization code) instance
with :meth:`CodeRequest.save_code(...)`, you may pass there as much extra
attributes, as you want, including `user_id`, for example.

Then, when you call :meth:`CodeExchangeRequest.exchange_for_token`, all these
attributes are copied to the :class:`AccessToken` instance. Therefore, token
you receive will contain all required extra fields, which you can use to show
user's data.


.. _Access Tokens Types: http://tools.ietf.org/html/rfc6749#section-7
.. _RFC 6750: http://tools.ietf.org/html/rfc6750


.. _getting_started_revoking_grant:

Revoking grant
--------------

Revoke all grants from a client:

.. code-block:: python

   >>> oauthist.revoke_grant(user_id, client_id)

Revoke particular access token

.. code-block:: python

   >>> oauthist.revoke_access_token(token_string)
