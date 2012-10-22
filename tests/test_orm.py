# -*- coding: utf-8 -*-
import mock
import pytest
import redis
from oauthist import orm


orm.configure(redis.Redis(), 'test_orm')

class User(orm.Model):
    _id_length = 16

class Book(orm.TaggedModel):
    pass

class TaggedUser(orm.TaggedAttrsModel):
    _exclude_attrs = ['name', ]

def setup_function(function):
    User.full_cleanup()
    Book.full_cleanup()


def teardown_function(function):
    User.full_cleanup()
    Book.full_cleanup()


def pytest_funcarg__user(request):
    user = User(1234, name='John Doe', age=30)
    user.save()
    request.addfinalizer(user.delete)
    return user


def pytest_funcarg__book(request):
    tags = ['foo', 'bar']
    book = Book(1234, tags=tags, title='How to Foo and Bar')
    book.save()
    request.addfinalizer(book.delete)
    return book


def pytest_funcarg__tagged_user(request):
    user = TaggedUser(1234, name='John Doe', age=30)
    user.save()
    request.addfinalizer(user.delete)
    return user


def pytest_funcarg__tags(request):
    return ['foo', 'bar']


#--- Basic functionality of models

def test_save_and_get(user):
    same_user = User.get(1234)
    assert same_user.name == 'John Doe'
    assert same_user.age == 30


def test_get_none():
    assert User.get(1234) is None


def test_update(user):
    user.set(name='Just Joe', gender='male')
    user.unset('age')
    user.save()
    same_user = User.get(1234)
    assert same_user.name == 'Just Joe'
    assert same_user.gender == 'male'
    with pytest.raises(AttributeError):
        same_user.age


def test_get_all(user):
    users = list(User.all())
    assert users == [user, ]


def test_delete(user):
    user.delete()
    user_count = len(list(User.all()))
    assert user_count == 0


#--- Test for tagged models

def test_tags_save_delete(book, tags):
    same_book = Book.get(book._id)
    assert set(same_book.tags) == set(tags)


def test_tags_find(book, tags):
    books = list(Book.find('foo'))
    assert books == [book, ]
    books = list(Book.find('bar'))
    assert books == [book, ]
    books = list(Book.find('foo', 'bar'))
    assert books == [book, ]


def test_tags_remove(book, tags):
    book.tags = ['foo', ]  # we removed the tag "bar"
    book.save()
    books = list(Book.find('bar'))
    assert books == []
    books = list(Book.find('foo'))
    assert books == [book, ]

#--- Test for tagged attrs models

def test_tagged_attrs_find(tagged_user):
    users = list(TaggedUser.find(age=30))
    assert users == [tagged_user, ]
    assert set(users[0].tags) == set(tagged_user.tags)


def test_exclude_tags(tagged_user):
    """
    test that TaggedUser._exclude_attrs works

    We don't tags for attributes, whose names are listed in _exclude_attrs
    property of the model
    """
    users = list(TaggedUser.find(name='John Doe'))
    assert users == []

#--- Test objects with no id

def test_auto_id():
    user = User(name='Foo bar')
    assert user._id is None
    user.save()
    assert user._id is not None

def test_auto_id_failed_random():
    with mock.patch('oauthist.orm.random_string') as random_string:
        random_string.return_value = '1234'
        User(name='Foo bar').save()
        with pytest.raises(RuntimeError):
            User(name='Foo bar').save()
