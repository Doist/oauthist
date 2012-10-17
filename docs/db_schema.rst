Database schema
===============

When we want to store object to the Redis database, we use :func:`store_object`
and :func:`restore_object` helper functions. These functions use picke module
methods to serialize and deserialize objects.

- ``clients``: set of client ids
- ``client:<id>``: object with information about the client
