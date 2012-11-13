# -*- coding: utf-8 -*-
import json
import ormist
from oauthist.core import framework
from oauthist.client import Client
from oauthist.authorization_code import Code
from oauthist.errors import OauthistValidationError, OauthistRuntimeError

JSON_HEADERS =  {
    'Content-Type': 'application/json;charset=UTF-8',
    'Cache-Control': 'no-store',
    'Pragma': 'no-cache',
}

class CodeExchangeRequest(object):

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
        self.check_invalid()
        if not self.access_token:
            self.access_token = AccessToken()
        # we have to copy all attributes from the code obj, besides
        # those which we don't need anymore
        code_attrs = self.code_obj.attrs.copy()
        for key in ('state', 'accepted', 'redirect_uri', 'expire'):
            code_attrs.pop(key, None)
        code_attrs.update(attrs)
        self.access_token.set(**code_attrs)
        self.access_token.set_expire(self.expire)
        self.access_token.save()
        return self.access_token

    def get_error(self):
        if not self.error:
            raise OauthistRuntimeError('Error attribute is not defined, maybe '
                                       'you forgot to call '
                                       'CodeExchangeRequest.is_invalid()')
        return AccessTokenError(self.error)


class AccessToken(ormist.TaggedAttrsModel):

    id_length = 64

    def to_werkzeug_response(self):
        from werkzeug.wrappers import Response
        content = self.get_json_content()
        return Response(json.dumps(content), headers=self.get_headers())

    def get_json_content(self):
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
        return JSON_HEADERS


class AccessTokenError(object):

    def __init__(self, error):
        self.error = error

    def to_werkzeug_response(self):
        from werkzeug.wrappers import Response
        content = self.get_json_content()
        return Response(json.dumps(content), headers=self.get_headers(),
                        status=400)

    def get_json_content(self):
        return {
            'error': self.error,
        }


    def get_headers(self):
        return JSON_HEADERS
