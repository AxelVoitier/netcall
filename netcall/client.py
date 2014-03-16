# vim: fileencoding=utf-8 et ts=4 sts=4 sw=4 tw=0 fdm=marker fmr=#{,#}

"""
Client classes to talk to a NetCall service.

Authors:

* Brian Granger
* Alexander Glyzov
"""

#-----------------------------------------------------------------------------
#  Copyright (C) 2012-2014. Brian Granger, Min Ragan-Kelley, Alexander Glyzov
#
#  Distributed under the terms of the BSD License.  The full license is in
#  the file LICENSE distributed as part of this software.
#-----------------------------------------------------------------------------

#-----------------------------------------------------------------------------
# Imports
#-----------------------------------------------------------------------------

from abc     import abstractmethod
from time    import time
from random  import randint
from logging import getLogger

import zmq

from zmq.utils               import jsonapi

from .base import RPCBase


logger = getLogger("netcall.client")


#-----------------------------------------------------------------------------
# RPC Service Proxy
#-----------------------------------------------------------------------------

class RPCClientBase(RPCBase):  #{
    """A service proxy to for talking to an RPCService."""

    def _create_socket(self):  #{
        super(RPCClientBase, self)._create_socket()

        self.socket = self.context.socket(zmq.DEALER)
        self.socket.setsockopt(zmq.IDENTITY, self.identity)
    #}
    def _build_request(self, method, args, kwargs, ignore=False):  #{
        req_id = b'%x' % randint(0, 0xFFFFFFFF)
        method = bytes(method)
        msg_list = [b'|', req_id, method]
        data_list = self._serializer.serialize_args_kwargs(args, kwargs)
        msg_list.extend(data_list)
        msg_list.append(bytes(int(ignore)))
        return req_id, msg_list
    #}
    def _parse_reply(self, msg_list):  #{
        """
        Parse a reply from service
        (should not raise an exception)

        The reply is received as a multipart message:

        [b'|', req_id, type, payload ...]

        Returns either None or a dict {
            'type'   : <message_type:bytes>       # ACK | OK | FAIL
            'req_id' : <id:bytes>,                # unique message id
            'srv_id' : <service_id:bytes> | None  # only for ACK messages
            'result' : <object>
        }
        """
        if len(msg_list) < 4 or msg_list[0] != b'|':
            logger.error('bad reply: %r' % msg_list)
            return None

        msg_type = msg_list[2]
        data     = msg_list[3:]
        result   = None
        srv_id   = None

        if msg_type == b'ACK':
            srv_id = data[0]
        elif msg_type == b'OK':
            try:
                result = self._serializer.deserialize_result(data)
            except Exception, e:
                msg_type = b'FAIL'
                result   = e
        elif msg_type == b'FAIL':
            try:
                error  = jsonapi.loads(msg_list[3])
                result = RemoteRPCError(error['ename'], error['evalue'], error['traceback'])
            except Exception, e:
                logger.error('unexpected error while decoding FAIL', exc_info=True)
                result = RPCError('unexpected error while decoding FAIL: %s' % e)
        else:
            result = RPCError('bad message type: %r' % msg_type)

        return dict(
            type   = msg_type,
            req_id = msg_list[1],
            srv_id = srv_id,
            result = result,
        )
    #}

    def __getattr__(self, name):  #{
        return RemoteMethod(self, name)
    #}

    @abstractmethod
    def call(self, proc_name, args=[], kwargs={}, ignore=False):  #{
        """
        Call the remote method with *args and **kwargs
        (may raise exception)

        Parameters
        ----------
        proc_name : <bytes> name of the remote procedure to call
        args      : <tuple> positional arguments of the remote procedure
        kwargs    : <dict>  keyword arguments of the remote procedure
        ignore    : <bool>  whether to ignore result or wait for it

        Returns
        -------
        result : <object>
            If the call succeeds, the result of the call will be returned.
            If the call fails, `RemoteRPCError` will be raised.
        """
        pass
    #}
#}

class SyncRPCClient(RPCClientBase):  #{
    """A synchronous service proxy whose requests will block."""

    def __init__(self, context=None, **kwargs):  #{
        """
        Parameters
        ==========
        context : Context
            An existing Context instance, if not passed, zmq.Context.instance()
            will be used.
        serializer : Serializer
            An instance of a Serializer subclass that will be used to serialize
            and deserialize args, kwargs and the result.
        """
        assert context is None or isinstance(context, zmq.Context)
        self.context = context if context is not None else zmq.Context.instance()
        super(SyncRPCClient, self).__init__(**kwargs)
    #}

    def call(self, proc_name, args=[], kwargs={}, ignore=False, timeout=None):  #{
        """
        Call the remote method with *args and **kwargs
        (may raise exception)

        Parameters
        ----------
        proc_name : <bytes> name of the remote procedure to call
        args      : <tuple> positional arguments of the remote procedure
        kwargs    : <dict>  keyword arguments of the remote procedure
        timeout : <float> | None
            Number of seconds to wait for a reply.
            RPCTimeoutError will be raised if no reply is received in time.
            Set to None, 0 or a negative number to disable.

        Returns
        -------
        <object>
            If the call succeeds, the result of the call will be returned.
            If the call fails, `RemoteRPCError` will be raised.
        """
        if not (timeout is None or isinstance(timeout, (int, float))):
            raise TypeError("timeout param: <float> or None expected, got %r" % timeout)

        if not self._ready:
            raise RuntimeError('bind or connect must be called first')

        req_id, msg_list = self._build_request(proc_name, args, kwargs, ignore)

        logger.debug('send: %r' % msg_list)
        self.socket.send_multipart(msg_list)

        if timeout and timeout > 0:
            poller = zmq.Poller()
            poller.register(self.socket, zmq.POLLIN)
            start_t    = time()
            deadline_t = start_t + timeout

            def recv_multipart():
                timeout_ms = int((deadline_t - time())*1000)  # in milliseconds
                #logger.debug('polling with timeout_ms=%s' % timeout_ms)
                if timeout_ms > 0 and poller.poll(timeout_ms):
                    msg = self.socket.recv_multipart()
                    return msg
                else:
                    raise RPCTimeoutError("Request %s timed out after %s sec" % (req_id, timeout))
        else:
            recv_multipart = self.socket.recv_multipart

        while True:
            msg_list = recv_multipart()
            logger.debug('received: %r' % msg_list)

            reply = self._parse_reply(msg_list)

            if reply is None \
            or reply['req_id'] != req_id:
                continue

            if reply['type'] == b'ACK':
                if ignore:
                    return None
                else:
                    continue

            if reply['type'] == b'OK':
                return reply['result']
            else:
                raise reply['result']
    #}
#}

class RemoteMethodBase(object):  #{
    """A remote method class to enable a nicer call syntax."""

    def __init__(self, client, method):
        self.client = client
        self.method = method
#}
class RemoteMethod(RemoteMethodBase):  #{

    def __call__(self, *args, **kwargs):  #{
        return self.client.call(self.method, args, kwargs)
    #}

    def __getattr__(self, name):  #{
        return RemoteMethod(self.client, '.'.join([self.method, name]))
    #}
#}

class RPCError(Exception):  #{
    pass
#}
class RemoteRPCError(RPCError):  #{
    """Error raised elsewhere"""
    ename = None
    evalue = None
    traceback = None

    def __init__(self, ename, evalue, tb):
        self.ename = ename
        self.evalue = evalue
        self.traceback = tb
        self.args = (ename, evalue)

    def __repr__(self):
        return "<RemoteError:%s(%s)>" % (self.ename, self.evalue)

    def __str__(self):
        sig = "%s(%s)" % (self.ename, self.evalue)
        if self.traceback:
            return self.traceback
        else:
            return sig
#}
class RPCTimeoutError(RPCError):  #{
    pass
#}

