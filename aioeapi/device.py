# -----------------------------------------------------------------------------
# System Imports
# -----------------------------------------------------------------------------

from typing import Optional, List, Union, Dict, AnyStr
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


# -----------------------------------------------------------------------------
#
#                                 CODE BEGINS
#
# -----------------------------------------------------------------------------


class Device(httpx.AsyncClient):
    """
    The Device class represents the async JSON-RPC client that communicates with
    an Arista EOS device.  This class inherits directly from the
    httpx.AsyncClient, so any initialization options can be passed directly.
    """

    auth = None
    EAPI_OFMT_OPTIONS = ("json", "text")
    EAPI_DEFAULT_OFMT = "json"

    def __init__(
        self,
        host: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        proto: Optional[str] = "https",
        port=None,
        **kwargs,
    ):
        """
        Initializes the Device class.  As a subclass to httpx.AsyncClient, the
        Caller can provide any of those initializers.  Specific paramertes for
        Device class are all optional and described below.

        Parameters
        ----------
        host: Optional[str]
            The EOS target device, either hostname (DNS) or ipaddress.

        username: Optional[str]
            The login user-name; requires the password parameter.

        password: Optional[str]
            The login password; requires the username parameter.

        proto: Optional[str]
            The protocol, http or https, to communicate eAPI with the device.

        port: Optional[Union[str,int]]
            If not provided, the proto value is used to lookup the associated
            port (http=80, https=443).  If provided, overrides the port used to
            communite with the device.

        Other Parameters
        ----------------
        base_url: str
            If provided, the complete URL to the device eAPI endpoint.

        auth:
            If provided, used as the httpx authorization initializer value. If
            not provided, then username+password is assumed by the Caller and
            used to create a BasicAuth instance.
        """

        port = port or getservbyname(proto)
        kwargs.setdefault("base_url", httpx.URL(f"{proto}://{host}:{port}"))
        kwargs.setdefault("verify", False)

        if username and password:
            self.auth = httpx.BasicAuth(username, password)

        kwargs.setdefault("auth", self.auth)

        super(Device, self).__init__(**kwargs)
        self.headers["Content-Type"] = "application/json-rpc"

    async def cli(
        self,
        command: Optional[AnyStr] = None,
        commands: Optional[List[AnyStr]] = None,
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
        """Used to create the JSON-RPC command dictionary object"""

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

    async def jsonrpc_exec(self, jsonrpc: dict) -> List[Union[Dict, AnyStr]]:
        """
        Execute the JSON-RPC dictionary object.

        Parameters
        ----------
        jsonrpc: dict
            The JSON-RPC as created by the `meth`:jsonrpc_command().

        Raises
        ------
        EapiCommandError
            In the event that a command resulted in an error response.

        Returns
        -------
        The list of command results; either dict or text depending on the
        JSON-RPC format pameter.
        """
        res = await self.post("/command-api", json=jsonrpc)
        res.raise_for_status()
        body = res.json()

        commands = jsonrpc["params"]["cmds"]
        ofmt = jsonrpc["params"]["format"]

        get_output = (lambda _r: _r["output"]) if ofmt == "text" else (lambda _r: _r)

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
