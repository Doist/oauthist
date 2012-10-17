# -*- coding: utf-8 -*-
# base error class
class OauthistError(Exception): pass

# lookup errors
class ClientNotFoundError(OauthistError): pass

# validation errors
class OauthistValidationError(OauthistError, ValueError): pass
