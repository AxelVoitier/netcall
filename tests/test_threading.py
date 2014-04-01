# vim: fileencoding=utf-8 et ts=4 sts=4 sw=4 tw=0 fdm=marker fmr=#{,#}

from netcall           import get_zmq_classes
from netcall.threading import ThreadPool, ThreadingRPCClient, ThreadingRPCService

from .base          import BaseCase
from .client_mixins import ClientBindConnectMixIn
from .rpc_mixins    import RPCCallsMixIn


class ThreadingBase(BaseCase):

    def setUp(self):
        Context, _ = get_zmq_classes()

        self.context = Context()
        self.pool    = ThreadPool(24)
        self.client  = ThreadingRPCClient(context=self.context, pool=self.pool)
        self.service = ThreadingRPCService(context=self.context, pool=self.pool)

        super(ThreadingBase, self).setUp()

    def tearDown(self):
        self.client.shutdown()
        self.service.shutdown()
        self.context.term()
        self.pool.close()
        self.pool.stop()
        self.pool.join()

        super(ThreadingBase, self).tearDown()


class ThreadingClientBindConnectTest(ClientBindConnectMixIn, ThreadingBase):
    pass

class ThreadingRPCCallsTest(RPCCallsMixIn, ThreadingBase):
    pass

