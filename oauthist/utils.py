#  -*- coding: utf-8 -*-
import pickle
import string
import random
import redis

class RandomGenerator(object):

    """
    Random generator amis to help random string and store unique values in db
    """

    DEFAULT_MAX_ITERATIONS = 10
    DEFAULT_CORPUS = string.ascii_letters + string.digits

    def __init__(self, redis, max_iterations=None, corpus=None):
        self.redis = redis
        self.max_iterations = max_iterations or self.DEFAULT_MAX_ITERATIONS
        self.corpus = corpus or self.DEFAULT_CORPUS

    def string(self, len):
        """
        Return random string with given len
        """
        return ''.join(random.choice(self.corpus) for _ in xrange(len))

    def insert_in_set(self, redis_key, len):
        """
        Add a new random string to set by its key and return just inserted value

        :param redis_key: the redis key name
        :param len: new length of the string
        :max_iterations: max number of attempts to find and insert
        """
        for _ in xrange(self.max_iterations):
            string = self.string(len)
            ret = self.redis.sadd(redis_key, string)
            if ret != 0:
                return string
        raise RuntimeError('Unable to insert unique random string in redis '
                           'database (key %r)' % redis_key)


def store_object(redis, key, obj):
    """
    Helper function to store object in redis db
    """
    value = pickle.dumps(obj)
    return redis.set(key, value)


def restore_object(redis, key):
    """
    Helper function to restore object from redis db
    """
    value = redis.get(key)
    if value is not None:
        return pickle.loads(value)
