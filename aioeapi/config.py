from typing import Optional
from .device import Device


class SessionConfig:
    """
    The SessionConfig instance is used to send configuration to a device using
    the EOS session mechanism.  This is the preferred way of managing
    configuraiton changes.
    """

    def __init__(self, device: Device, name: str):
        """
        Creates a new instance of the session config instance bound
        to the given device instance, and using the session `name`.

        Parameters
        ----------
        device:
            The associated device instance

        name:
            The name of the config session
        """
        self._device = device
        self._cli = device.cli
        self._name = name
        self._cli_config_session = f"configure session {self.name}"

    # -------------------------------------------------------------------------
    # properties for read-only attributes
    # -------------------------------------------------------------------------

    @property
    def name(self) -> str:
        """returns read-only session name attribute"""
        return self._name

    @property
    def device(self) -> Device:
        """returns read-only device instance attribute"""
        return self._device

    # -------------------------------------------------------------------------
    #                               Public Methods
    # -------------------------------------------------------------------------

    async def status_all(self) -> dict:
        """
        Get the status of the session config by running the command:
            # show configuration sessions detail

        Returns
        -------
        dict object of native EOS eAPI response; see `status` method for
        details.
        """
        return await self._cli("show configuration sessions detail")

    async def status(self) -> dict | None:
        """
        Get the status of the session config by running the command:
            # show configuration sessions detail

        And returning only the status dictionary for this session. If you want
        all sessions, then use the `status_all` method.

        Returns
        -------
        Dict instance of the session status.  If the session does not exist,
        then this method will return None.

        The native eAPI results from JSON output, see exmaple:

        Examples
        --------
        all results:
            {
                "maxSavedSessions": 1,
                "maxOpenSessions": 5,
                "sessions": {
                    "jeremy1": {
                        "instances": {},
                        "state": "pending",
                        "commitUser": "",
                        "description": ""
                    },
                    "ansible_167510439362": {
                        "instances": {},
                        "state": "completed",
                        "commitUser": "joe.bob",
                        "description": "",
                        "completedTime": 1675104396.4500246
                    }
                }
            }

        if the session name was 'jeremy1', then this method would return
            {
                "instances": {},
                "state": "pending",
                "commitUser": "",
                "description": ""
            }
        """
        res = await self.status_all()
        return res["sessions"].get(self.name)

    async def push(self, content: list[str], replace: Optional[bool] = False):
        """
        Sends the configuration content to the device.  If `replace` is true,
        then the command "rollback clean-config" is issued before sendig the
        configuration content.

        Parameters
        ----------
        content: list[str]
            The text configuration CLI commands, as a list of strings, that
            will be sent to the device.

        replace: bool
            When True, the content will replace the existing configuration
            on the device.

        Returns
        -------
        """
        commands = [self._cli_config_session, *content]
        if replace:
            commands.insert(1, "rollback clean-config")

        await self._cli(commands=commands)

    async def commit(self, timer: Optional[str] = None):
        """
        Commits the session config using the commands
            # configure session <name>
            # commit

        If the timer is specified, format is "hh:mm:ss", then a commit timer is
        started.  A second commit action must be made to confirm the config
        session before the timer expires; otherwise the config-session is
        automatically aborted.
        """
        command = (
            f"{self._cli_config_session} commit timer {timer}"
            if timer
            else f"{self._cli_config_session} commit timer"
        )

        await self._cli(command)

    async def abort(self):
        """
        Aborts the configuration session using the command:
            # configure session <name> abort
        """
        await self._cli(f"{self._cli_config_session} abort")

    async def diff(self) -> str:
        """
        Returns the "diff" of the session config relative to the running config, using
        the command:
            # show session-config named <name> diffs

        Returns
        -------
        Returns a string in diff-patch format.

        References
        ----------
          * https://www.gnu.org/software/diffutils/manual/diffutils.txt
        """
        return await self._cli(
            f"show session-config named {self.name} diffs", ofmt="text"
        )

    async def write(self):
        """
        Saves the running config to the startup config by issuing the command
        "write" to the device.
        """
        await self._cli("write")
