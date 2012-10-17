# -*- coding: utf-8 -*-
from oauthist.utils import restore_object, store_object


class Client(object):

    def __init__(self, fw, client_id, client_type, redirect_url,
                 client_secret=None, attrs=None):
        """
        Create a new client instance from scratch

        It is supposed that this method is never used from the client code, but
        instead methods of framework are invoked.

        :param fw: a framework instance
        :param client_id: random client id, already registered in the "clients"
                          Redis set
        :param client_type: string with client type
        :param redirect_url: string or list of strings with redurect urls
        :param client_secret: client secret (for confidential clients only)
        :param attrs: extra attributes
        """
        self.fw = fw
        self.id = client_id
        self.type = client_type
        self.redirect_url = redirect_url
        self.secret = client_secret
        self.attrs = attrs or {}

    @classmethod
    def from_db(cls, fw, client_id):
        key = fw._key('client:{0}', client_id)
        value = restore_object(fw.redis, key)
        return cls.deserialize(fw, value)

    @classmethod
    def deserialize(cls, fw, json_value):
        return cls(fw, json_value['id'], json_value['type'], json_value['redirect_url'],
                   client_secret=json_value['secret'], attrs=json_value['attrs'])

    def serialize(self):
        return {
            'id': self.id,
            'type': self.type,
            'redirect_url': self.redirect_url,
            'secret': self.secret,
            'attrs': self.attrs,
        }

    def delete(self):
        return self.fw.redis.delete(self._key())

    def save(self):
        return store_object(self.fw.redis, self._key(), self.serialize())

    def _key(self):
        return self.fw._key('client:{0}', self.id)

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False
        return self.serialize() == other.serialize()

    def __repr__(self):
        return '<%s client %s>' % (self.type, self.id)
