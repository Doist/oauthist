# -*- coding: utf-8 -*-
# base error class
class OauthistError(Exception): pass

# runtime error
class OauthistRuntimeError(OauthistError):
    """
    Runtime error which should not occur in normal circumstances

    Raises if there is a suspicious that server developer uses framework
    incorrectly
    """
    pass

# lookup errors
class ClientNotFoundError(OauthistError): pass

# validation errors
class OauthistValidationError(OauthistError, ValueError): pass

# invalid access token
class InvalidAccessToken(OauthistError): pass
