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
  to condigure connection to Redis server
- :option:`scopes` (optional): list of strings, defining allowed
  `access token scopes`_. If not defined, all scopes are accepted.
- :option:`authorization_code_timeout` (optional): expiration timeout of
  authorization code in seconds (by default, 3600).
- :option:`access_token_timeout` (optional): expiration timeout of access token
  (by default ``None`` which means that token never expires unless explicitly
  revoked)
- :option:`prefix` (recommended): the string prefix which will be used to store
  and search for keys in Redis database

Sample initialization:

.. code-block:: python

   >>> oauthist.configure(prefix='oauthist')

.. _getting_started_creating_clients:

Creating clients
----------------

According to the specification, before starting to use API calls, every client
should be registered with the `client registration`_. From the point of view of
OAuth server, the only two arguments here are required:

- :option:`client_type`: the type of client, according to OAuth sepcification
  (can be either "web", "user-agent" or "native")
- :option:`redirect_uri`: redirection URI (string) or the set of accepted
  redirection URIs (list of strings).

.. note:: to prevent the "`Open Redirectors`_" type of attacks, all possible
          redirection URLs must be explicitly set up on the configuration step.

A new random client-id will be generated, and for client of "web" type a shared
secret will also be issued

.. code-block:: python

   >>> extra_kwargs = dict(name='My Client', description='Hello world')
   >>> client = oauthist.register_client(client_type='web',
                                         redirect_uri='http://example.com/oauth2cb',
                                         **extra_kwargs)
   >>> client.id
   'ORG8hSAuTEb762AO'
   >>> client.secret
   'cx2kQAPjtCKlUGvwQPYA6yZ22OXDTrV5SbrGafqzHzGXQcDIgsI5uyCaLI8emjGn'
   >>> client.name
   'My Client'

All arguments, passed as extra kwargs, will be stored in the Redis, and can be
accessed as object attributes.

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
code in its GET argument. The authorization server must ensure that user is
logged in, all passed arguments are valid, and user agrees to authorize Client.

Before starting the process of building the response user, we must ensure that
request hasn't been forged in some way. It is important, because we must never
send redirect to invalid or forged callback URI:

 If the request fails due to a missing, invalid, or mismatching
 redirection URI, or if the client identifier is missing or invalid,
 the authorization server SHOULD inform the resource owner of the
 error and MUST NOT automatically redirect the user-agent to the
 invalid redirection URI.

Basically, we should consider three possible outcomes:

- all steps passed successfully, create the code and make the redirect.
- set of scopes or something else is invalid, or user refused to grant access,
  then create the error message and make the redirect
- redirect URI is suspicious / invalid. Don't redirect, but instead show the
  error message right into the website interface.

If user is turns out to be logged in, and he/she confirms the authorization,
you call the :func:`get_redirect` function.

Depending on the validity of client id, redirect uri and other parameters,
function may return redirect object (subclass of strings) or raise the exception
:class:`oauthist.InvalidRequest`.

Create the :class:`CodeRequest` object

.. code-block:: python

   >>> req = oauthist.CodeRequest(client_id='...',
   ...                             redirect_uri='http://...',
   ...                             scope='...',
   ...                             state='...')

If you use `Werkzeug`_ or the framework based on it, you may call

.. code-block:: python

   >>> req = oauthist.CodeRequest.from_werkzeug(request)

Then you should check if the request is itself valid, and if it is makes
sense to go on with it. If the request is invalid (suspicious, forged, etc),
you must stop handling it, and show the error message. The validation is easy.

.. code-block:: python

   >>> if not req.is_valid():
   ...     return render('error.html', error=req.error)


Now, as request seems valid, you may perform some additional checks (the most
important step is to ask user for confirmation), and then can issue the code or
return the error.

As we have to connect the issued code with the user you've just registered,
you should pass ``user_id`` parameter to the function. It may be the integer
or the string, if you don't use integers as user ids.

.. code-block:: python

   >>> redirect_uri = req.get_redirect(user_id=user_id)
   >>> str(redirect_uri)
   'http://...?code=<...>&state=<...>'
   >>> redirect_uri.succeeded
   True
   >>> redirect_uri.failed
   False
   >>> redirect_uri.code
   '...'
   >>> redirect_uri.scope
   ['...', '...', '...']

If all you want is to send the redirect, then just pass the return value to the
HTTP redirect function of your framework. Additionally, you can get some extra
parameters as object attributes.

If you want to return error instead of issuing the code, use another argument of
the same function.

.. code-block:: python

   >>> redirect_url = req.get_redirect(error='access_denied')

See `4.1.2.1 Error Response`_ section of RFC for more variants of error argument.

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

   >>> req = oauthist.CodeExchangeRequest(client_id='...',
                                           client_secret='...',
                                           redirect_uri='...',
                                           code='...')

Similarly, if you're a lucky `Werkzeug`_ user, you can create the object
by its Request.

.. code-block:: python

   >>> req = oauthist.CodeExchangeRequest.from_werkzeug(request)

Then do exchange it for access token

.. code-block:: python

   >>> resp = req.exchange_for_token()


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


Response can be failed. For example, if no such code found. You can validate the
request before issuing the code, but usually it's not required.

.. code-block:: python


   >>> req.is_valid()
   False
   >>> resp = req.exchange_for_token()
   >>> resp.get_code()
   400
   >>> resp.succeeded
   False
   >>> resp.failed
   True

Refreshing access token
~~~~~~~~~~~~~~~~~~~~~~~

OAuth2 server intentionally doesn't issue refresh tokens, as we strive to keep
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


If you want to return error

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

It's up to you to check whether username and password are valid, the framework
provides convenient objects and methods to extract data and to build,
store and return the access key.

Create the code exchange request

.. code-block:: python

   >>> req = oauthist.PasswordExchangeRequest(username='...',
                                               password='...',
                                               client_id='...',
                                               client_secret='...',
                                               scope='...')


Parameters `client_id` and `client_secret` are required for private client;
as `client_secret` doesn't exist for public client, there is nothing to pass
here; and finally, `client_id` for public client is optional.

Then you must check the username and password, and exchange the request for
token or return the error response.

Below is a sample which may be used in Django code (mind
:class:`User.DoesNotExist` exception though).

.. code-block:: python

   >>> user = User.objects.get(username=req.username)
   >>> if user.check_password(req.password):
   ...     resp = req.exchange_for_token(user_id=user.id)
   ... else:
   ...     resp = req.get_error_response('invalid_client')


.. _getting_started_verifying_requests:

Verifying requests with access tokens
--------------------------------------

The way access tokens should be used is defined in the `Access Tokens Types`_
chapter of RFC 6749.

The framework supports Bearer Tokens (see `RFC 6750`_). According to the
recommendation, the token can be passed in ``Access:`` HTTP header, in POST or
GET request as a parameter.

Once you received the bearer token string, you must check if it is valid to your
scope. If the token is valid, the :class:`AccessToken` object will be returned,
otherwise :class:`InvalidAccessToken` exception will be raised.

.. code-block:: python

   >>> token = oauthist.check_access_token(token_string, 'scopeA', 'scopeA-B')

Token has :attr:`user_id` field which you could use then to perform actions
on behalf of it.

.. note:: The successful response will be returned, if token is valid **either**
          for 'scopeA' **or** 'scopeA-B'. If for some reasons you want to ensure
          that token is valid for **both** scopes, use cycle

          .. code-block:: python

             try:
                 for scope in scopes:
                 token = oauthist.check_access_token(token_string, scope)
             except oauthist.InvalidAccessToken as e:
                 # handle exception here
                 pass

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
