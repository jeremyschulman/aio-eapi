# -----------------------------------------------------------------------------
# System Imports
# -----------------------------------------------------------------------------

from typing import Optional, List
from socket import getservbyname

# -----------------------------------------------------------------------------
# Public Imports
# -----------------------------------------------------------------------------

import httpx

# -----------------------------------------------------------------------------
# Exports
# -----------------------------------------------------------------------------


__all__ = ["Device"]


class EapiCommandError(RuntimeError):
    def __init__(self, failed, errmsg, passed, not_exec):
        self.failed = (failed,)
        self.errmsg = errmsg
        self.passed = passed
        self.not_exec = not_exec
        super(EapiCommandError, self).__init__()


# -----------------------------------------------------------------------------
#
#                                 CODE BEGINS
#
# -----------------------------------------------------------------------------


class Device(httpx.AsyncClient):
    auth = None
    EAPI_OFMT_OPTIONS = ("json", "text")
    EAPI_DEFAULT_OFMT = "json"

    def __init__(
        self,
        host,
        username: Optional[str] = None,
        password: Optional[str] = None,
        proto: Optional[str] = "https",
        port=None,
        **kwargs,
    ):
        port = port or getservbyname(proto)
        kwargs.setdefault("verify", False)
        kwargs.setdefault(
            "auth", self.auth or httpx.BasicAuth(username=username, password=password)
        )

        super(Device, self).__init__(
            base_url=httpx.URL(f"{proto}://{host}:{port}"), **kwargs
        )

        self.headers["Content-Type"] = "application/json-rpc"

    async def cli(
        self,
        command: Optional[str] = None,
        commands: Optional[List[str]] = None,
        **kwargs,
    ):
        """
        Execute one or more CLI commands.

        Parameters
        ----------
        command: str
            A single command to execute; results in a single output response

        commands: List[str]
            A list of commands to executes; results in a list of output responses

        Other Parameters
        ----------------
        ofmt: str
            Either 'json' or 'text'; indicates the output fromat for the CLI commands.

        autoComplete: Optional[bool] = False
            Enabled/disables the command auto-compelete feature of the EAPI.  Per the
            documentation:
                Allows users to use short hand commands in eAPI calls. With this
                parameter included a user can send 'sh ver' via eAPI to get the
                output of 'show version'.

        expandAliases: Optional[bool] = False
            Enables/disables the command use of User defined alias.  Per the
            documentation:
                Allowed users to provide the expandAliases parameter to eAPI
                calls. This allows users to use aliased commands via the API.
                For example if an alias is configured as 'sv' for 'show version'
                then an API call with sv and the expandAliases parameter will
                return the output of show version.

        Returns
        -------
        One or List of output respones, per the description above.
        """
        if not any((command, commands)):
            raise RuntimeError("Required 'command' or 'commands'")

        jsonrpc = self.jsoncrpc_command(
            commands=[command] if command else commands, **kwargs
        )
        res = await self.jsonrpc_exec(jsonrpc)
        return res[0] if command else res

    def jsoncrpc_command(self, commands, **kwargs) -> dict:
        cmd = {
            "jsonrpc": "2.0",
            "method": "runCmds",
            "params": {
                "version": 1,
                "cmds": commands,
                "format": kwargs.get("ofmt") or self.EAPI_DEFAULT_OFMT,
            },
            "id": str(kwargs.get("req_id") or id(self)),
        }
        if "autoComplete" in kwargs:
            cmd["params"]["autoComplete"] = kwargs["autoComplete"]

        if "expandAliases" in kwargs:
            cmd["params"]["expandAliases"] = kwargs["expandAliases"]

        return cmd

    async def jsonrpc_exec(self, jsonrpc: dict):
        res = await self.post("/command-api", json=jsonrpc)
        res.raise_for_status()
        body = res.json()

        commands = jsonrpc["params"]["cmds"]
        ofmt = jsonrpc["params"]["format"]

        if ofmt == "text":

            def get_output(_cmd_r):
                return _cmd_r["output"]

        else:

            def get_output(_cmd_r):
                return _cmd_r

        # if there are no errors then return the list of command results.

        if (err_data := body.get("error")) is None:
            return [get_output(cmd_res) for cmd_res in body["result"]]

        # ----------------------------------------------------------------
        # if we are here, then there were some command errors.  Raise a
        # RuntimeError exception with args (commands that failed, passed,
        # not-executed).
        # ----------------------------------------------------------------

        cmd_data = err_data["data"]
        len_data = len(cmd_data)
        err_at = len_data - 1
        err_msg = err_data["message"]

        raise EapiCommandError(
            passed=[
                get_output(cmd_data[cmd_i])
                for cmd_i, cmd in enumerate(commands[:err_at])
            ],
            failed=commands[err_at],
            errmsg=err_msg,
            not_exec=commands[err_at + 1 :],
        )
