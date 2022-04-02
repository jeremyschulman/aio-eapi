import httpx


class EapiCommandError(RuntimeError):
    """
    Exception class for EAPI command errors

    Attributes
    ----------
    failed: str - the failed command
    errmsg: str - a description of the failure reason
    passed: List[dict] - a list of command results of the commands that passed
    not_exec: List[str] - a list of commands that were not executed
    """

    def __init__(self, failed, errmsg, passed, not_exec):
        """Initializer for the EapiCommandError exception"""
        self.failed = failed
        self.errmsg = errmsg
        self.passed = passed
        self.not_exec = not_exec
        super(EapiCommandError, self).__init__()


# alias for exception during sending-receiving
EapiTransportError = httpx.HTTPStatusError
