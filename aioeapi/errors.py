from __future__ import annotations

import httpx

from typing import Union, Any


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

    # pylint: disable=too-many-arguments
    def __init__(
        self,
        failed: str,
        errors: list[str],
        errmsg: str,
        passed: list[Union[str, dict[str, Any]]],
        not_exec: list[dict[str, Any]],
    ):
        """Initializer for the EapiCommandError exception"""
        self.failed = failed
        self.errors = errors
        self.errmsg = errmsg
        self.passed = passed
        self.not_exec = not_exec
        super().__init__()

    def __str__(self) -> str:
        """returns the error message associated with the exception"""
        return self.errmsg


# alias for exception during sending-receiving
EapiTransportError = httpx.HTTPStatusError
