# -*- coding: utf-8 -*-
import os
from setuptools import setup

def read(fname):
    try:
        return open(os.path.join(os.path.dirname(__file__), fname)).read()
    except IOError:
        return ''

setup(
    name = 'oauthist',
    version = '0.1',
    author = 'Roman Imankulov',
    author_email = 'roman.imankulkov@gmail.com',
    description = ('OAuth2 framework to implement resource and '
                   'authorization servers. Uses Redis as the shared storage for '
                   'all required data'),
    license = 'BSD',
    keywords = 'library framework oauth oauth2 redis authentication',
    url = 'http://wedoist.com',
    packages = ['oauthist', ],
    long_description = read('README.rst'),
    install_requires = ['redis', 'ormist>=0.1,==dev', ],
    # see here for more details on syntax
    # https://groups.google.com/d/msg/python-virtualenv/CwcGLlecT0o/4_JClCuYSjEJ
    # Version must be defined explicitly
    dependency_links = [
        'http://github.com/Doist/ormist/tarball/master#egg=ormist-dev',
    ],
    classifiers = [
        'Development Status :: 4 - Beta',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Topic :: Internet',
        'Topic :: Software Development :: Libraries',
        'License :: OSI Approved :: BSD License',
    ],
)
