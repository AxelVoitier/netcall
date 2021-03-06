# vim: fileencoding=utf-8 et ts=4 sts=4 sw=4 tw=0 fdm=marker fmr=#{,#}


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
