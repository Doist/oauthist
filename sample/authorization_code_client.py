# -*- coding: utf-8 -*-
"""
Sample web-application (OAuth2 client), following authorization code grant flow
"""
import sys
import random
import requests
import urllib
from flask import Flask, render_template, session, request, redirect

app = Flask(__name__)
app.secret_key = 'a random secret key to make flask sessions work'

CLIENT_ID = '1234'
CLIENT_SECRET = 'foobarbaz'
CLIENT_HOST = 'http://localhost:5001'
SERVER_HOST = 'http://localhost:5002'
REDIRECT_URLS = ['%s/oauth2cb' % CLIENT_HOST, ]
OAUTHIST_SCOPES = ['user_data', 'document_list']


@app.route('/')
def index():
    """
    Index page.

    We build an oauth2 authentication link (`link` variable). This link is a
    starting point for code-based authentication process.

    Note that we set up oauth2cb as the callback URL, there we receive the
    response either with `code` parameter in GET args, or `error`
    if user refuses to grant access.
    """
    base_url = '%s/authorize' % SERVER_HOST
    oauth_state = str(random.randint(0, sys.maxint))
    args = {
        'response_type': 'code',
        'client_id': CLIENT_ID,
        'redirect_uri': REDIRECT_URLS[0],
        'scope': ' '.join(OAUTHIST_SCOPES),
        'state': oauth_state,
    }
    link = '%s?%s' % (base_url, urllib.urlencode(args))
    session['oauth_state'] = oauth_state
    return render_template('client/index.html', link=link,
                           server_host=SERVER_HOST)


@app.route('/oauth2cb')
def oauth2cb():
    """
    Callback page.

    User will be redirected to this page after visiting server oauth2
    authorization endpoint.

    Note that prevent possible attacks, we compare the state argument with
    the one we stored in session (see :func:`index` code).

    If response contains "error" argument, we display the error. if the "code"
    value is found we exchange it to access token (direct HTTP request to Oauth2
    endpoint).

    If access token is received, then we store it to user session and redirect
    user to the /access URL, which tries to get access to user's data on the
    server.
    """
    state = request.args.get('state')
    session_state = session.pop('oauth_state', None)
    if not session_state or session_state != state:
        return render_template('client/oauth2cb_missing_state.html')
    error = request.args.get('error')
    if error:
        return render_template('client/oauth2cb_error.html', error=error)
    code = request.args.get('code')
    if not code:
        return render_template('client/oauth2cb_unrecognized_response.html')
    # exchange code for access token
    base_url = '%s/access_token'  % SERVER_HOST
    data = {
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': REDIRECT_URLS[0],
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'state': state,
    }
    resp = requests.post(base_url, data=data)
    resp_json = resp.json()
    session['access_token'] = resp_json['access_token']
    return redirect('/access')


@app.route('/access')
def access():
    """
    Get access to user's data.

    We make direct HTTP request to server API endpoint. Oauth protocol doesn't
    specify neither the address of the endpoint, nor the format of returning
    data, all it does is defines the way how access token should be passed to
    the server (either in GET or POST, or in Authorization header). Here we
    send the request with access token in GET, and expect JSON response from
    the server.
    """
    access_token = session.get('access_token')
    user_data_url = '%s/api/user_data' % SERVER_HOST
    resp = requests.get(user_data_url, params={'access_token': access_token})
    return render_template('client/access.html', url=user_data_url, response=resp)


if __name__ == '__main__':
    app.run(port=5001, debug=True, host='0.0.0.0')
