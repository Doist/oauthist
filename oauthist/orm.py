# -*- coding: utf-8 -*-
"""
ORM -- object-to-redis mapper

.. code-block:: python

    from oauthist import orm

    r = redis.Redis()
    orm.configure(r, prefix='foo')

    class User(orm.Model):
        pass

    user = User(1234, name='John Doe', age=30)
    user.save()
    # created two records
    # foo:user:__all__ with set (1234)
    # foo:user:object:1234 with {name: 'John Doe', 'age': 30}

    user = User.get(1234)
    # returns the same user object as it was

    user.unset('age')
    user.set(name='Just John', gender='male')
    user.save()
    # alters the same object by removing "age", adding "gender" and changing "name" fields

    users = User.objects.all()
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
import threading
import pickle
import string
import random
import re

#--- ORM object

orm = threading.local()

def configure(redis, prefix):
    """
    configure the ORM
    """
    orm.redis = redis
    orm.prefix = prefix


#--- Metaclass magic

class ModelBase(type):
    """
    Metaclass for Model and its subclasses

    Used to set up a manager for model. Class constructor searches
    for model_manager instance and adds the reference to
    """
    def __new__(cls, name, parents, attrs):
        model_manager = attrs.pop('objects', None)
        if not model_manager:
            parent_mgrs = filter(None, [getattr(p, 'objects', None) for p in parents])
            mgr_class = parent_mgrs[0].__class__
            model_manager = mgr_class()
        attrs['objects'] = model_manager
        model_manager.model_name = attrs.pop('model_name', to_underscore(name))
        model_manager.id_length = attrs.pop('id_length', 16)
        ret = type.__new__(cls, name, parents, attrs)
        model_manager.model = ret
        return ret

def to_underscore(name):
    """
    Helper function converting CamelCase to underscore: camel_case
    """
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()


#-- The real model code is here

class ModelManager(object):
    # metaclass ModelBase ensures this object has "model_name", "id_length"
    # and "model" attribute,

    def _key(self, key, *args, **kwargs):
        prefix = orm.prefix
        model_name = self.model_name
        if prefix:
            template = '{0}:{1}:{2}'.format(prefix, model_name, key)
        else:
            template = '{0}:{1}'.format(model_name, key)

        if args or kwargs:
            template = template.format(*args, **kwargs)
        return template

    def full_cleanup(self):
        key = self._key('*')
        keys = orm.redis.keys(key)
        if keys:
            orm.redis.delete(*keys)

    def get(self, _id):
        key = self._key('object:{0}', _id)
        value = orm.redis.get(key)
        if value:
            kwargs = pickle.loads(value)
            return self.model(_id, **kwargs)

    def reserve_random_id(self, max_attempts=10):
        key = self._key('__all__')
        for _ in xrange(max_attempts):
            value = random_string(self.id_length)
            ret = orm.redis.sadd(key, value)
            if ret != 0:
                return value
        raise RuntimeError('Unable to reserve random id for model "%s"' % self.model_name)

    def all(self):
        all_key = self._key('__all__')
        ids = []
        if orm.redis.exists(all_key):
            ids = orm.redis.smembers(all_key)
        for _id in ids:
            yield self.get(_id)


class Model(object):
    """
    Base model class
    """
    __metaclass__ = ModelBase
    objects = ModelManager()


    def __init__(self, _id=None, **attrs):
        if _id is not None:
            _id = str(_id)
        self._id = _id
        self.attrs = attrs

    def __getattr__(self, attr):
        try:
            return self.attrs[attr]
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
            self._id = self.objects.reserve_random_id()
        all_key = self.objects._key('__all__')
        key = self.objects._key('object:{0}', self._id)
        value = pickle.dumps(self.attrs)
        pipe = orm.redis.pipeline()
        pipe.sadd(all_key, self._id)
        pipe.set(key, value)
        pipe.execute()

    def delete(self):
        all_key = self.objects._key('__all__')
        key = self.objects._key('object:{0}', self._id)
        pipe = orm.redis.pipeline()
        pipe.srem(all_key, self._id)
        pipe.delete(key)
        pipe.execute()

    def set(self, **kwargs):
        self.attrs.update(**kwargs)

    def unset(self, *args):
        for arg in args:
            self.attrs.pop(arg, None)



class TaggedModelManager(ModelManager):

    def get(self, _id):
        instance = super(TaggedModelManager, self).get(_id)
        if instance:
            tags_key = self._key('object:{0}:tags', _id)
            tags = orm.redis.smembers(tags_key) or []
            instance.tags = tags
        return instance

    def find(self, *tags):
        if not tags:
            return
        keys = []
        for tag in tags:
            key = self._key('tags:{0}', tag)
            keys.append(key)
        ids = orm.redis.sinter(*keys)
        for _id in ids:
            yield self.get(_id)


class TaggedModel(Model):
    """
    Model with tags support
    """

    objects = TaggedModelManager()

    def __init__(self, _id=None, tags=None, **kwargs):
        super(TaggedModel, self).__init__(_id, **kwargs)
        self.tags = tags or []
        self._saved_tags = self.tags

    def save(self):
        super(TaggedModel, self).save()
        if not self.tags:
            return
        pipe = orm.redis.pipeline()
        tags_key = self.objects._key('object:{0}:tags', self._id)
        pipe.sadd(tags_key, *self.tags)
        for tag in self.tags:
            key = self.objects._key('tags:{0}', tag)
            pipe.sadd(key, self._id)
        for tag_to_rm in set(self._saved_tags) - set(self.tags):
            key = self.objects._key('tags:{0}', tag_to_rm)
            pipe.srem(key, self._id)
        pipe.execute()
        self._saved_tags = self.tags


class TaggedAttrsModelManager(TaggedModelManager):

    def __init__(self, exclude_attrs=None):
        self.exclude_attrs = set(exclude_attrs or [])

    def attrs_to_tags(self, attrs):
        tags = []
        for k, v in attrs.iteritems():
            if k not in self.exclude_attrs:
                tags.append(u'{0}:{1}'.format(unicode(k), unicode(v)))
        return tags

    def find(self, **attrs):
        tags = self.attrs_to_tags(attrs)
        for instance in super(TaggedAttrsModelManager, self).find(*tags):
            yield instance

class TaggedAttrsModel(TaggedModel):

    objects = TaggedAttrsModelManager(exclude_attrs=[])

    def __init__(self, _id=None, **attrs):
        tags = self.objects.attrs_to_tags(attrs)
        super(TaggedAttrsModel, self).__init__(_id, tags, **attrs)

    def set(self, **kwargs):
        super(TaggedAttrsModel, self).set(**kwargs)
        self.tags = self.objects.attrs_to_tags(self.attrs)

    def unset(self, *args):
        super(TaggedAttrsModel, self).unset(*args)
        self.tags = self.objects.attrs_to_tags(self.attrs)


def random_string(len, corpus=None):
    """
    Return random string with given len
    """
    if not corpus:
        corpus = string.ascii_letters + string.digits
    return ''.join(random.choice(corpus) for _ in xrange(len))


def expire_to_datetime(expire, ts=None):
    """
    Convert datetime(), timedelta() or number of seconds to datetime object

    :param expire: the expiration mark (None, seconds, datetime or timedelta)
    :param ts: if defined, then use its value instead of datetime.now()
               for relative expiration timestamps

    :returns: datetime object, which is "naive" but considered as having UTC
              timezone
    """
    if expire is None:
        return None
    if isinstance(expire, datetime.datetime):
        return expire
    if not ts:
        ts = datetime.datetime.utcnow()
    if isinstance(expire, datetime.timedelta):
        return ts + expire
    return ts + datetime.timedelta(seconds=expire)


def datetime_to_timestamp(dt):
    """
    Convert datetime objects to correct timestamps

    Consider naive datetimes as UTC ones
    """
    if dt is None:
        return None
    micro = dt.microsecond / 1e6
    ts = calendar.timegm(dt.timetuple())
    return ts + micro


def timestamp_to_datetime(ts):
    """
    Convert timestamps to datetime objects
    """
    if ts is None:
        return None
    return datetime.datetime.utcfromtimestamp(ts)
