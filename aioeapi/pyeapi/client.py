#
# Copyright (c) 2014, Arista Networks, Inc.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met:
#
#   Redistributions of source code must retain the above copyright notice,
#   this list of conditions and the following disclaimer.
#
#   Redistributions in binary form must reproduce the above copyright
#   notice, this list of conditions and the following disclaimer in the
#   documentation and/or other materials provided with the distribution.
#
#   Neither the name of Arista Networks nor the names of its
#   contributors may be used to endorse or promote products derived from
#   this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL ARISTA NETWORKS
# BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR
# BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
# WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE
# OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN
# IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#

from uuid import uuid4
import re

from functools import lru_cache
import asyncio

from .eapilib import CommandError
from .utils import CliVariants, load_module, make_iterable

class Node(object):
    """Represents a single device for sending and receiving eAPI messages

    The Node object provides an instance for communicating with Arista EOS
    devices.  The Node object provides easy to use methods for sending both
    enable and config commands to the device using a specific transport.  This
    object forms the base for communicating with devices.

    Attributes:
        connection (EapiConnection): The connection property represents the
            underlying transport used by the Node object to communicate
            with the device using eAPI.
        running_config (str): The running-config from the device.  This
            property is lazily loaded and refreshed over the life cycle of
            the instance.
        startup_config (str): The startup-config from the device.  This
            property is lazily loaded and refreshed over the life cycle of
            the instance.
        autorefresh (bool): If True, the running-config and startup-config are
            refreshed on config events.  If False, then the config properties
            must be manually refreshed.
        config_defaults (bool): If True, the default config options will be
            shown in the running-config output
        settings (dict): Provides access to the settings used to create the
            Node instance.

    Args:
        connection (EapiConnection): An instance of EapiConnection used as the
            transport for sending and receiving eAPI requests and responses.
        **kwargs: An arbitrary list of keyword arguments
    """
    def __init__(self, connection, **kwargs):
        self._connection = connection
        self._running_config = None
        self._startup_config = None
        self._version = None
        self._version_number = None
        self._model = None
        self._session_name = None

        self._dev = kwargs.get('dev')

        self._enablepwd = kwargs.get('enablepwd')
        self.autorefresh = kwargs.get('autorefresh', True)
        self.config_defaults = kwargs.get('config_defaults', True)
        self.settings = kwargs

    def __str__(self):
        return 'Node(connection=%s)' % str(self._connection)

    def __repr__(self):
        return 'Node(connection=%s)' % repr(self._connection)

    def _sync_to_async_(func, *args, **kwargs):
        try:
            loop = asyncio.get_event_loop()
            
            if loop.is_running():
                loop.create_task(func(*args, **kwargs))
            else:
                loop.run_until_complete(func(*args, **kwargs))
        except Exception:
            pass

    @property
    def connection(self):
        if self._connection:
            return self._connection
        else:
            return self._dev

    @property
    def running_config(self):
        if self._running_config is not None:
            return self._running_config
        params = 'all' if self.config_defaults else None
        self._running_config = self._sync_to_async_(self.get_config(params=params,
                                                as_string=True))
        return self._running_config

    @property
    def startup_config(self):
        if self._startup_config is not None:
            return self._startup_config
        self._startup_config = self._sync_to_async_(self.get_config('startup-config',
                                                as_string=True))
        return self._startup_config

    @property
    def version(self):
        if self._version:
            return self._version
        self._sync_to_async_(self._get_version_properties)
        return self._version

    @property
    def version_number(self):
        if self._version_number:
            return self._version_number
        self._sync_to_async_(self._get_version_properties)
        return self._version_number

    @property
    def model(self):
        if self._model:
            return self._model
        self._sync_to_async_(self._get_version_properties)
        return self._model

    async def _get_version_properties(self):
        """Parses version and model information out of 'show version' output
        and uses the output to populate class properties.
        """
        # Parse out version info
        output = await self.enable('show version')
        self._version = str(output[0]['result']['version'])
        match = re.match(r'[\d.\d]+', str(output[0]['result']['version']))
        if match:
            self._version_number = str(match.group(0))
        else:
            self._version_number = str(output[0]['result']['version'])
        # Parse out model number
        match = re.search(r'\d\d\d\d', str(output[0]['result']['modelName']))
        if match:
            self._model = str(match.group(0))
        else:
            self._model = str(output[0]['result']['modelName'])

    def enable_authentication(self, password):
        """Configures the enable mode authentication password

        EOS supports an additional password authentication mechanism for
        sessions that want to switch to executive (or enable) mode.  This
        method will configure the password, if required, for entering
        executive mode

        Args:
            password (str): The password string in clear text used to
                authenticate to exec mode
        """
        self._enablepwd = str(password).strip()

    async def config(self, commands, **kwargs):
        """Configures the node with the specified commands

        This method is used to send configuration commands to the node.  It
        will take either a string, list or CliVariants type and prepend the
        necessary commands to put the session into config mode.
        pyeapi.utils.CliVariants facilitates alternative executions to commands
        sequence until one variant succeeds or all fail

        Args:
            commands (str, list, CliVariants): The commands to send to the node
                in config mode. If the commands argument is an str or
                CliVariants type, it will be cast to a list.
                The list of commands will also be prepended with the necessary
                commands to put the session in config mode.
                CliVariants could be part of a list too, however only a single
                occurrence of CliVariants type in commands is supported.
                CliVariants type facilitates execution of alternative commands
                sequences, e.g.:
                ``config( [cli1, CliVariants( cli2, cli3 ), cli4] )``
                the example above can be translated into following sequence:
                ``config( [cli1, cli2, cli4] )``
                ``config( [cli1, cli3, cli4] )``
                CliVariants accepts 2 or more arguments of str, list type, or
                their mix. Each argument to CliVariants will be joined with the
                rest of commands and all command sequences will be tried until
                one variant succeeds. If all variants fail the last failure
                exception will be re-raised.

            **kwargs: Additional keyword arguments for expanded eAPI
                functionality. Only supported eAPI params are used in building
                the request

        Returns:
            The config method will return a list of dictionaries with the
                output from each command.  The function will strip the
                response from any commands it prepends.
        """
        def variant_cli_idx( cmds ):
            # return index of first occurrence of CliVariants type in cmds
            try:
                return [ type(v) for v in cmds ].index( CliVariants )
            except (ValueError):
                return -1

        cfg_call = self._configure_session if self._session_name \
            else self._configure_terminal

        if isinstance( commands, CliVariants ):
            commands = [ commands ]
        idx = variant_cli_idx( commands )
        if idx == -1:
            return await cfg_call( commands, **kwargs )

        # commands contain CliVariants obj, e.g.: [ '...', CliVariants, ... ]
        err = None
        for variant in commands[ idx ].variants:
            cmd = commands[ :idx ] + variant + commands[ idx + 1: ]
            try:
                return await cfg_call( cmd, **kwargs )
            except (CommandError) as exp:
                err = exp
        raise err  # re-raising last occurred CommandError


    async def _configure_terminal(self, commands, **kwargs):
        """Configures the node with the specified commands with leading
        "configure terminal"
        """
        commands = make_iterable(commands)
        commands = list(commands)

        # push the configure command onto the command stack
        commands.insert(0, 'configure terminal')
        response = await self.run_commands(commands, **kwargs)
        # after config change the _chunkify lru_cache has to be cleared
        self._chunkify.cache_clear()

        if self.autorefresh:
            self.refresh()

        # pop the configure command output off the stack
        response.pop(0)

        return response

    async def _configure_session(self, commands, **kwargs):
        """Configures the node with the specified commands with leading
        "configure session <session name>"
        """
        if not self._session_name:
            raise CommandError(-1, 'Not currently in a session')

        commands = make_iterable(commands)
        commands = list(commands)

        # push the configure command onto the command stack
        commands.insert(0, 'configure session %s' % self._session_name)
        response = await self.run_commands(commands, **kwargs)
        # after config change the _chunkify lru_cache has to be cleared
        self._chunkify.cache_clear()

        # pop the configure command output off the stack
        response.pop(0)

        return response

    @lru_cache(maxsize=None)
    def _chunkify( self, config, indent=0 ):
        """parse device config and return a dict holding sections and
        sub-sections:
        - a section always begins with a line with zero indents,
        - a sub-section always begins with an indented line
        a (sub)section typically contains a begin line (with a lower indent)
        and a body (with a higher indent). A section might be degenerative (no
        body, just the section line itself), while sub-sections always contain
        a sub-section line plus some body). E.g., here's a snippet of a section
        dict:
        {   ...
            'spanning-tree mode none': 'spanning-tree mode none\n',
            ...
            'mac security': 'mac security\n  profile PR\n    cipher aes256-gcm',
            '   profile PR': '  profile PR\n    cipher aes256-gcm'
            ... }

        it's imperative that the most outer call is made with indent=0, as the
        indent parameter defines processing of nested sub-sections, i.e., if
        indent > 0, then it's a recursive call and `config` argument contains
        last parsed (sub)section, which in turn may contain sub-sections
        """
        def is_subsection_present( section, indent ):
            return any( line[ indent ] == ' ' for line in section )

        def get_indent( line ):
            return len( line ) - len( line.lstrip() )

        sections = {}
        key = None
        banner = None
        for line in config.splitlines( keepends=True )[ indent > 0: ]:
            line_rs = line.rstrip()
            if indent == 0:
                if banner:
                    sections[ banner ] += line
                    if line_rs == 'EOF':
                        banner = None
                    continue
                if line.startswith( 'banner ' ):
                    banner = line_rs
                    sections[ banner ] = line
                    continue
            if get_indent( line_rs ) > indent:  # i.e. subsection line
                # key is always expected to be set by now
                sections[ key ] += line
                continue
            subsection = sections.get( key, '' ).splitlines()[ 1: ]
            if subsection:
                sub_indent = get_indent( subsection[0] )
                if is_subsection_present( subsection, sub_indent ):
                    parsed = self._chunkify( sections[key], indent=sub_indent )
                    parsed.update( sections )
                    sections = parsed
            key = line_rs
            sections[ key ] = line
        return sections

    def section(self, regex, config='running_config'):
        """Returns a section of the config

        Args:
            regex (str): A valid regular expression used to select sections
                of configuration to return
            config (str): The configuration to return.  Valid values for config
                are "running_config" or "startup_config".  The default value
                is "running_config"

        Returns:
            The configuration section as a string object.
        """
        if config in ['running_config', 'startup_config']:
            config = getattr(self, config)
        chunked = self._chunkify(config)
        r = re.compile(regex)
        matching_keys = [k for k in chunked.keys() if r.search(k)]
        if len(matching_keys) == 0:
            raise TypeError('config section not found')
        matching_key = matching_keys[0]
        match = chunked[matching_key]
        return match

    async def enable(self, commands, encoding='json', strict=False,
               send_enable=True, **kwargs):
        """Sends the array of commands to the node in enable mode

        This method will send the commands to the node and evaluate
        the results.  If a command fails due to an encoding error,
        then the command set will be re-issued individual with text
        encoding.

        Args:
            commands (list): The list of commands to send to the node

            encoding (str): The requested encoding of the command output.
                Valid values for encoding are JSON or text

            strict (bool): If False, this method will attempt to run a
                command with text encoding if JSON encoding fails
            send_enable (bool): If True the enable command will be
                                prepended to the command list automatically.
            **kwargs: Additional keyword arguments for expanded eAPI
                functionality. Only supported eAPI params are used in building
                the request

        Returns:
            A dict object that includes the response for each command along
                with the encoding

        Raises:
            TypeError:
                This method does not support sending configure
                commands and will raise a TypeError if configuration commands
                are found in the list of commands provided

                This method will also raise a TypeError if the specified
                encoding is not one of 'json' or 'text'

            CommandError: This method will raise a CommandError if any one
                of the commands fails.
        """
        commands = make_iterable(commands)

        if 'configure' in commands:
            raise TypeError('config mode commands not supported')

        results = list()
        # IMPORTANT: There are two keys (response, result) that both
        # return the same value. 'response' was originally placed
        # there in error and both are now present to avoid breaking
        # existing scripts. 'response' will be removed in a future release.
        if strict:
            responses = await self.run_commands(commands, encoding, send_enable,
                                          **kwargs)
            for index, response in enumerate(responses):
                results.append(dict(command=commands[index],
                                    result=response,
                                    response=response,
                                    encoding=encoding))
        else:
            for command in commands:
                try:
                    resp = await self.run_commands(command, encoding, send_enable,
                                             **kwargs)
                    results.append(dict(command=command,
                                        result=resp[0],
                                        encoding=encoding))
                except CommandError as exc:
                    if exc.error_code == 1003:
                        resp = await self.run_commands(command, 'text', send_enable,
                                                 **kwargs)
                        results.append(dict(command=command,
                                            result=resp[0],
                                            encoding='text'))
                    else:
                        raise
        return results

    async def run_commands(self, commands, encoding='json', send_enable=True,
                     **kwargs):
        """Sends the commands over the transport to the device

        This method sends the commands to the device using the nodes
        transport.  This is a lower layer function that shouldn't normally
        need to be used, preferring instead to use config() or enable().

        Args:
            commands (list): The ordered list of commands to send to the
                device using the transport
            encoding (str): The encoding method to use for the request and
                excpected response.
            send_enable (bool): If True the enable command will be
                                prepended to the command list automatically.
            **kwargs: Additional keyword arguments for expanded eAPI
                functionality. Only supported eAPI params are used in building
                the request

        Returns:
            This method will return the raw response from the connection
                which is a Python dictionary object.
        """
        commands = make_iterable(commands)

        # Some commands are multiline commands. These are banner commands and
        # SSL commands. So with this two lines we
        # can support those by passing commands by doing:
        # banner login MULTILINE: This is my banner.\nAnd I even support
        # multiple lines.
        # Why this? To be able to read a configuration from a file, split it
        # into lines and pass it as it is
        # to pyeapi without caring about multiline commands.
        commands = [{'cmd': c.split('MULTILINE:')[0],
                    'input': '%s\n' % (c.split('MULTILINE:')[1].strip())}
                    if 'MULTILINE:' in c else c for c in commands]

        if send_enable:
            if self._enablepwd:
                commands.insert(0, {'cmd': 'enable', 'input': self._enablepwd})
            else:
                commands.insert(0, 'enable')

        if self._connection:
            response = self._connection.execute(commands, encoding, **kwargs)
        
            # pop enable command from the response only if we sent enable
            if send_enable:
                response['result'].pop(0)

            return response['result']
        else:
            response = await self._dev.cli(commands=commands, ofmt=encoding, **kwargs)

            # pop enable command from the response only if we sent enable
            if send_enable:
                response.pop(0)
                
            return response

    def api(self, name, namespace='.pyeapi.api'):
        """Loads the specified api module

        This method is the API autoload mechanism that will load the API
        module specified by the name argument.  The API module will be loaded
        and look first for an initialize() function and secondly for an
        instance() function.  In both cases, the node object is passed to
        the module.

        Args:
            name (str): The name of the module to load.  The name should be
                the name of the python file to import
            namespace (str): The namespace to use to load the module.  The
                default value is 'pyeapi.api'

        Returns:
            The API module loaded with the node instance.
        """
        module = load_module('{}.{}'.format(namespace, name))
        if hasattr(module, 'initialize'):
            module.initialize(self)
        if hasattr(module, 'instance'):
            return module.instance(self)
        return module

    async def get_config(self, config='running-config', params=None,
                    as_string=False):
        """ Retreives the config from the node

        This method will retrieve the config from the node as either a string
        or a list object.  The config to retrieve can be specified as either
        the startup-config or the running-config.

        Args:
            config (str): Specifies to return either the nodes startup-config
                or running-config.  The default value is the running-config
            params (str): A string of keywords to append to the command for
                retrieving the config.
            as_string (boo): Flag that determines the response.  If True, then
                the configuration is returned as a raw string.  If False, then
                the configuration is returned as a list.  The default value is
                False

        Returns:
            This method will return either a string or a list depending on the
            states of the as_string keyword argument.

        Raises:
            TypeError: If the specified config is not one of either
                'running-config' or 'startup-config'
        """
        if config not in ['startup-config', 'running-config']:
            raise TypeError('invalid config name specified')

        command = 'show %s' % config
        if params:
            command += ' %s' % params

        result = await self.run_commands(command, 'text')
        if as_string:
            return str(result[0]['output']).strip()

        return str(result[0]['output']).split('\n')

    def refresh(self):
        """Refreshes the instance config properties

        This method will refresh the public running_config and startup_config
        properites.  Since the properties are lazily loaded, this method will
        clear the current internal instance variables.  One the next call the
        instance variables will be repopulated with the current config

        """
        self._running_config = None
        self._startup_config = None

    def configure_session(self):
        """Enter a config session
        """
        self._session_name = self._session_name or uuid4()

    async def diff(self):
        """Returns session-config diffs in text encoding

        Note: "show session-config diffs" doesn't support json encoding
        """
        response = await self._configure_session(
            ['show session-config diffs'], encoding='text' )

        return response[0]['output']

    async def commit(self):
        """Commits the current config session
        """
        return await self._configure_and_exit_session(['commit'])

    async def abort(self):
        """Aborts the current config session
        """
        return await self._configure_session(['abort'])

    async def _configure_and_exit_session(self, commands, **kwargs):
        response = await self._configure_session(commands, **kwargs)

        if self.autorefresh:
            self.refresh()

        # Exit the current config session
        self._session_name = None

        return response
