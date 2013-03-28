# -*- coding: utf-8 -*-
import oauthist
from resources import resources

resources.register_mod('tests.resources_oauthist')


def setup_function(func):
    oauthist.configure()
    oauthist.client_mgr.start()



def teardown_function(func):
    oauthist.full_cleanup()
