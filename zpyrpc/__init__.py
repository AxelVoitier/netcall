"""A simple but fast RPC library for Python using ZeroMQ.

Authors:

* Brian Granger
* Alexander Glyzov

Example
-------

To create a simple service::

    from zpyrpc import TornadoRPCService
    class Echo(TornadoRPCService):

        @rpc_method
        def echo(self, s):
            return s

    echo = Echo()
    echo.bind('tcp://127.0.0.1:5555')
    echo.start()
    echo.serve()

To talk to this service::

    from zpyrpc import SyncRPCClient
    p = SyncRPCClient()
    p.connect('tcp://127.0.0.1:5555')
    p.echo('Hi there')
    'Hi there'
"""

#-----------------------------------------------------------------------------
#  Copyright (C) 2012-2014. Brian Granger, Min Ragan-Kelley, Alexander Glyzov
#
#  Distributed under the terms of the BSD License.  The full license is in
#  the file COPYING.BSD, distributed as part of this software.
#-----------------------------------------------------------------------------

#-----------------------------------------------------------------------------
# Imports
#-----------------------------------------------------------------------------

# Notice: for gevent versions of the classes import zpyrc.green

from .service import TornadoRPCService, rpc_method
from .client  import (
    SyncRPCClient, TornadoRPCClient, AsyncRemoteMethod, RemoteMethod,
    RPCError, RemoteRPCError, RPCTimeoutError
)
from .serializer import *

