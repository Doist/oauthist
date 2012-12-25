# -*- coding: utf-8 -*-
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


@app.route('/', methods=['POST', 'GET', ])
def index():
    """
    Index page.

    We ask for user_id and password, and make a direct HTTP request to the server.
    In turn, server should return either the access token, or an error message.
    """
    response_text = None

    if request.method == 'POST':

        # make the request to get access token
        base_url = '%s/access_token'  % SERVER_HOST
        data = {
            'grant_type': 'password',
            'username': request.form['username'],
            'password': request.form['password'],
            'scope': ' '.join(OAUTHIST_SCOPES),
            'client_id': CLIENT_ID,
            'client_secret': CLIENT_SECRET,
        }
        resp = requests.post(base_url, data=data)
        if resp.status_code == 200:
            resp_json = resp.json()
            session['access_token'] = resp_json['access_token']
            return redirect('/access')

        response_text = resp.text

    return render_template('client/user_password_index.html',
                           response_text=response_text,
                           server_host=SERVER_HOST)

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
