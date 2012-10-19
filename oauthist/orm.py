# -*- coding: utf-8 -*-
"""
ORM -- object-to-redis mapper

.. code-block:: python

    r = redis.Redis()
    orm = ORM(r, prefix='foo')

    class User(orm.Model):
        pass

    user = User(1234, name='John Doe', age=30)
    user.save()
    # created two records
    # foo:user:__all__ with set (1234)
    # foo:user:object:1234 with {name: 'John Doe', 'age': 30}

    user = User.get(1234)
    # returns the same user object as it was

    user.delete('age')
    user.set(name='Just John', gender='male')
    user.save()
    # alters the same object by removing "age", adding "gender" and changing "name" fields

    users = User.all()
    # return all users we have


    class Book(orm.TaggedModel):
        pass

    book = Book(1234, tags=['compsci', 'python', 'programming'], title='Dive into Python')
    book.save()
    # creates the record
    # foo:book:__all__ with set (1234)
    # foo:book:object:1234 with {title: 'Dive into python'}
    # foo:book:object:1234:tags with set (compsci, python, programming)
    # foo:book:tags:compsci with set (1234)
    # foo:book:tags:python with set (1234)
    # foo:book:tags:programming with set (1234)

    books = Book.filter(tags=['compsci', 'python'])
    # this addtional method returns the list of one item

    class User2(orm.TaggedAttrsModel):
        pass

    # this is a shortcut, which just adds a tag to every attribute you write
    # in the database


"""
import pickle
import string
import random
import re

#--- ORM object

class ORM(object):
    """
    ORM object (generic settings for all models)
    """

    def __init__(self, redis, prefix=None):
        self.redis = redis
        self.prefix = prefix
        # here we create inner classes for this ORM
        class_attrs = {'_orm': self}
        self.Model = type('Model', (Model, ),class_attrs)
        self.TaggedModel = type('TaggedModel', (TaggedModel, ), class_attrs)
        self.TaggedAttrsModel = type('TaggedAttrsModel', (TaggedAttrsModel, ), class_attrs)


#--- Metaclass magic

class ModelBase(type):
    """
    Metaclass for Model and its subclasses
    """

    def __new__(cls, name, parents, attrs):
        if not '_model_name' in attrs:
            attrs['_model_name'] = to_underscore(name)
        return type.__new__(cls, name, parents, attrs)

def to_underscore(name):
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()


#-- The real model code is here

class Model(object):
    """
    Base model class
    """
    __metaclass__ = ModelBase

    @classmethod
    def _key(cls, key, *args, **kwargs):
        prefix = cls._orm.prefix
        model_name = cls._model_name
        if prefix:
            template = '{0}:{1}:{2}'.format(prefix, model_name, key)
        else:
            template = '{0}:{1}'.format(model_name, key)

        if args or kwargs:
            template = template.format(*args, **kwargs)
        return template

    @classmethod
    def full_cleanup(cls):
        key = cls._key('*')
        keys = cls._orm.redis.keys(key)
        if keys:
            cls._orm.redis.delete(*keys)

    @classmethod
    def get(cls, _id):
        key = cls._key('object:{0}', _id)
        value = cls._orm.redis.get(key)
        if value:
            kwargs = pickle.loads(value)
            return cls(_id, **kwargs)

    @classmethod
    def reserve_random_id(cls, max_attempts=10):
        key = cls._key('__all__')
        for _ in xrange(max_attempts):
            ret = cls._orm.redis.sadd(key, random_string(cls._id_length))
            if ret != 0:
                return string
        raise RuntimeError('Unable to reserve random id for model "%s"' % cls._model_name)

    @classmethod
    def all(cls):
        all_key = cls._key('__all__')
        ids = []
        if cls._orm.redis.exists(all_key):
            ids = cls._orm.redis.smembers(all_key)
        for _id in ids:
            yield cls.get(_id)

    def __init__(self, _id=None, **kwargs):
        if _id is not None:
            _id = str(_id)
        self._id = _id
        self.kwargs = kwargs

    def __getattr__(self, attr):
        try:
            return self.kwargs[attr]
        except KeyError as e:
            raise AttributeError(e)

    def __eq__(self, other):
        if other.__class__ != self.__class__:
            return False
        return self._id == other._id

    def __repr__(self):
        return '<%s id:%s>' % (self.__class__.__name__, self._id)

    def save(self):
        if self._id is None:
            self._id = self.reserve_random_id()
        all_key = self._key('__all__')
        key = self._key('object:{0}', self._id)
        value = pickle.dumps(self.kwargs)
        pipe = self._orm.redis.pipeline()
        pipe.sadd(all_key, self._id)
        pipe.set(key, value)
        pipe.execute()

    def delete(self):
        all_key = self._key('__all__')
        key = self._key('object:{0}', self._id)
        pipe = self._orm.redis.pipeline()
        pipe.srem(all_key, self._id)
        pipe.delete(key)
        pipe.execute()

    def set(self, **kwargs):
        self.kwargs.update(**kwargs)

    def unset(self, *args):
        for arg in args:
            self.kwargs.pop(arg, None)



class TaggedModel(Model):
    """
    Model with tags support
    """

    def __init__(self, _id=None, tags=None, **kwargs):
        super(TaggedModel, self).__init__(_id, **kwargs)
        self.tags = tags or []

    def save(self):
        super(TaggedModel, self).save()
        if not self.tags:
            return
        pipe = self._orm.redis.pipeline()
        tags_key = self._key('object:{0}:tags', self._id)
        pipe.sadd(tags_key, *self.tags)
        for tag in self.tags:
            key = self._key('tags:{0}', tag)
            pipe.sadd(key, self._id)
            pipe.execute()

    @classmethod
    def get(cls, _id):
        key = cls._key('object:{0}', _id)
        value = cls._orm.redis.get(key)
        if value:
            kwargs = pickle.loads(value)
            tags_key = cls._key('object:{0}:tags', _id)
            tags = cls._orm.redis.smembers(tags_key) or []
            return cls(_id, tags=tags, **kwargs)

    @classmethod
    def find(cls, *tags):
        if not tags:
            return
        keys = []
        for tag in tags:
            key = cls._key('tags:{0}', tag)
            keys.append(key)
        ids = cls._orm.redis.sinter(*keys)
        for _id in ids:
            yield cls.get(_id)


class TaggedAttrsModel(TaggedModel):

    @classmethod
    def kwargs_to_tags(cls, kwargs):
        tags = []
        for k, v in kwargs.iteritems():
            tags.append(u'{0}:{1}'.format(unicode(k), unicode(v)))
        return tags

    @classmethod
    def get(cls, _id):
        key = cls._key('object:{0}', _id)
        value = cls._orm.redis.get(key)
        if value:
            kwargs = pickle.loads(value)
            return cls(_id, **kwargs)

    @classmethod
    def find(cls, **kwargs):
        tags = cls.kwargs_to_tags(kwargs)
        if not tags:
            return
        keys = []
        for tag in tags:
            key = cls._key('tags:{0}', tag)
            keys.append(key)
        ids = cls._orm.redis.sinter(*keys)
        for _id in ids:
            yield cls.get(_id)


    def __init__(self, _id=None, **kwargs):
        tags = self.kwargs_to_tags(kwargs)
        super(TaggedAttrsModel, self).__init__(_id, tags, **kwargs)


def random_string(len, corpus=None):
    """
    Return random string with given len
    """
    if not corpus:
        corpus = string.ascii_letters + string.digits
    return ''.join(random.choice(corpus) for _ in xrange(len))
