from typing import Optional, AnyStr, Tuple, List

import json
from socket import getservbyname
import httpx
import base64
from collections import namedtuple


__all__ = ["Device", "CommandResults"]


CommandResults = namedtuple("CommandResults", ["ok", "command", "output"])


class Transport(object):
    OFMT_OPTIONS = ("json", "text")

    def __init__(self, host, proto, port, creds, timeout=60):
        port = port or getservbyname(proto)
        self.client = httpx.AsyncClient(
            base_url=httpx.URL(f"{proto}://{host}:{port}"),
            verify=False,
            timeout=httpx.Timeout(timeout),
        )

        self.client.headers["Content-Type"] = "application/json-rpc"
        self.b64auth = (
            base64.encodebytes(bytes("%s:%s" % creds, encoding="utf-8"))
            .decode()
            .replace("\n", "")
        )
        self.client.headers["Authorization"] = "Basic %s" % self.b64auth

        self.username = creds[0]
        self.ofmt = "json"

    @property
    def timeout(self):
        return self.client.timeout

    @timeout.setter
    def timeout(self, value):
        self.client.timeout = httpx.Timeout(value)

    def form_command(self, commands, **kwargs) -> dict:
        cmd = {
            "jsonrpc": "2.0",
            "method": "runCmds",
            "params": {
                "version": 1,
                "cmds": commands,
                "format": kwargs.get("ofmt") or self.ofmt,
            },
            "id": str(kwargs.get("req_id") or id(self)),
        }
        if "autoComplete" in kwargs:
            cmd["params"]["autoComplete"] = kwargs["autoComplete"]

        if "expandAliases" in kwargs:
            cmd["params"]["expandAliases"] = kwargs["expandAliases"]

        return cmd

    async def post(self, jsonrpc, ofmt=None):
        res = await self.client.post("/command-api", json=jsonrpc)
        res.raise_for_status()
        body = res.json()

        commands = jsonrpc["params"]["cmds"]

        if ofmt == "text":

            def get_output(_cmd_r):
                return _cmd_r["output"]

        else:

            def get_output(_cmd_r):
                return _cmd_r

        if (err_data := body.get("error")) is None:
            return [
                CommandResults(
                    ok=True, command=commands[cmd_i], output=get_output(cmd_res)
                )
                for cmd_i, cmd_res in enumerate(body["result"])
            ]

        post_res = list()
        cmd_data = err_data["data"]
        len_data = len(cmd_data)
        err_at = len_data - 1
        err_msg = err_data["message"]

        # commands the passed
        for cmd_i, cmd in enumerate(commands[:err_at]):
            post_res.append(
                CommandResults(ok=True, command=cmd, output=get_output(cmd_data[cmd_i]))
            )

        # the command that failed
        post_res.append(
            CommandResults(ok=False, command=commands[err_at], output=err_msg)
        )

        # all other commands not executed
        for cmd in commands[err_at + 1 :]:
            post_res.append(CommandResults(ok=False, command=cmd, output=None))

        return post_res


class Device(object):
    def __init__(
        self,
        host: AnyStr,
        creds: Tuple[str, str],
        proto: Optional[AnyStr] = "https",
        port=None,
        private=None,
    ):
        self.host = host
        self.private = private
        self.api = Transport(host=host, creds=creds, proto=proto, port=port)

    async def exec(self, commands: List[AnyStr], **kwargs) -> List[CommandResults]:
        """
        Execute a list of operational commands and return the output as a list of CommandResults.
        """
        xcmd = self.api.form_command(commands=commands, **kwargs)
        return await self.api.post(xcmd, **kwargs)

    async def get_config(self, ofmt="text") -> List[CommandResults]:
        xmcd = self.api.form_command(commands=["show running-config"], ofmt=ofmt)
        return await self.api.post(xmcd, ofmt=ofmt)

    async def push_config(
        self, contents: str, enter_cmds=None, exit_cmds=None, ofmt="text"
    ) -> List[CommandResults]:
        config_cmds = contents.strip().splitlines()
        if not enter_cmds:
            config_cmds.insert(0, "configure")
        else:
            config_cmds[0:0] = enter_cmds

        if exit_cmds:
            config_cmds.extend(exit_cmds)

        jsonrpc = self.api.form_command(commands=config_cmds, ofmt=ofmt)
        return await self.api.post(jsonrpc=jsonrpc, ofmt=ofmt)
