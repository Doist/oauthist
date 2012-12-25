# -*- coding: utf-8 -*-
import json
from flask import Flask, render_template, request, redirect, abort, make_response
from oauthist import (configure, Client, CodeRequest, Code, CodeExchangeRequest,
                      InvalidAccessToken, ProtectedResourceRequest, AccessTokenError, PasswordExchangeRequest)

app = Flask(__name__)

USER_ID = '1'
CLIENT_ID = '1234'
CLIENT_SECRET = 'foobarbaz'
CLIENT_HOST = 'http://localhost:5001'
SERVER_HOST = 'http://localhost:5002'
REDIRECT_URLS = ['%s/oauth2cb' % CLIENT_HOST, ]
OAUTHIST_SCOPES = ['user_data', 'document_list']
JSON_CONTENT_TYPE = 'application/json; charset=UTF-8'

# Fake users database
USERS = {
    '1': {'name': 'John Doe', 'email': 'jdoe@example.com', 'password': 'foo'},
    '2': {'name': 'Robert Roe', 'email': 'rroe@example.com', 'password': 'bar'},
}

def setup():
    configure(scopes=OAUTHIST_SCOPES)
    client = Client(CLIENT_ID,
                    client_type='web',
                    client_secret=CLIENT_SECRET,
                    redirect_urls=REDIRECT_URLS,
                    name='Test Client')
    client.save()


@app.route('/authorize')
def authorize():
    """
    Authorization endpoint.

    This controller receives requests from clients via user's web-browsers,
    check whether the request if formally correct (by invoking `is_broken`
    and `is_invalid` methods), and shows to users the confirmation page, where
    they should accept or decline the request.

    Accept/decline form leads to `authorize_confirmation` page.
    """
    code_req = CodeRequest.from_werkzeug(request)
    if code_req.is_broken():
        return render_template('server/authorize_broken.html',
                               error=code_req.error)
    if code_req.is_invalid():
        return redirect(code_req.get_redirect())

    # at this point we save the code request and wait for user confirmation
    code = code_req.save_code(user_id=USER_ID)
    return render_template('server/authorize_confirmation.html', code=code,
                           client=code_req.client)


@app.route('/authorize/confirmation', methods=['POST', ])
def authorize_confirmation():
    """
    Authorization confirmation.

    This is the controller handling POST results of user's choice.

    We handle form results in the way which is not specified by OAuth2 protocol
    and redirect user's browser back to client website either with authorization
    code or with error message in the URL.

    Note that we have a placeholder for CSRF protection here. In the real
    application you must use the real CSRF protection code instead.
    """
    if request.form.get('_csrf_token') != 'random-value':
        abort(400)
    code_id = request.form.get('code')
    resolution = request.form.get('resolution')
    code = Code.objects.get(code_id)
    if not code or resolution not in ('accept', 'decline'):
        return render_template('server/authorize_broken.html',
                               error='malformed_request')
    # if user declined request, remove it and send error response to the server
    # with appropriate error status
    if resolution == 'decline':
        return redirect(code.decline())
    # otherwise we confirm  request code, and send redirect with all required
    # data
    else:
        return redirect(code.accept())


@app.route('/access_token', methods=['POST', ])
def access_token():
    """
    Token endpoint.

    This endpoint exchanges HTTP requests containing authorization codes and
    client requsites to access token, suitable for making API access.

    The interaction is performed "behind the scenes" between client and server
    without any user involvement.
    """
    def verify_requisites(username, password):
        """
        callback function verifying requisites and returning None or dict
        which should be associated with AccessToken. In this particular
        example we consider user_id as username
        """
        user = USERS.get(username)
        if not user:
            return None
        if password != user['password']:
            return None
        ret = {'user_id': username}
        ret.update(user)
        return ret


    grant_type = request.form.get('grant_type')
    if grant_type == 'authorization_code':
        req = CodeExchangeRequest.from_werkzeug(request)
    elif grant_type == 'password':
        req = PasswordExchangeRequest.from_werkzeug(request, verify_requisites)
    else:
        return AccessTokenError('invalid_request').to_werkzeug_response()

    if req.is_invalid():
        return req.get_error().to_werkzeug_response()
    access_token = req.exchange_for_token()
    return access_token.to_werkzeug_response()

#--- API controllers (to show how to work with it)

@app.route('/api/user_data')
def user_data():
    """
    API endpoint.

    The only OAuth2-concerned part here is access token extraction and
    verification. As soon as client is verified and user is identified, the
    application builds a response in the way, which is out of the OAuth2
    specification scope.
    """
    req = ProtectedResourceRequest.from_werkzeug(request)
    try:
        access_token = req.verify_access_token()
    except InvalidAccessToken:
        resp = make_response(json.dumps({'error': 'access denied'}), 400)
    else:
        user = USERS[access_token.user_id]
        resp = make_response(json.dumps(user))
    resp.content_type = JSON_CONTENT_TYPE
    return resp


if __name__ == '__main__':
    setup()
    app.run(port=5002, debug=True, host='0.0.0.0')
