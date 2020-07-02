# Arista EOS API asyncio Client

This repository contains an Arista EOS asyncio client.

**WORK IN PROGESS**

### Quick Example

Thie following shows how to create a Device instance and run a list of
commands.

By default the Device instance will use HTTPS transport.  The Device instance
supports the following settings:

   * `host` - The device hostname or IP address
   * `username` - The login user-name
   * `password` - The login password
   * `proto` - *(Optional)* Choose either "https" or "http", defaults to "https"
   * `port` - *(Optional)* Chose the protocol port to override proto default

The result of command execution is a list of CommandResults (namedtuple).
The `output` field will be:
   * dict when output format is 'json' (*default*)
   * str when output format is 'text'

```python
from asynceapi import Device

username = 'dummy-user'
password = 'dummy-password'

async def run_test(host):
    dev = Device(host=host, creds=(username, password))
    res = await dev.exec(['show hostname', 'show version'])
    for cmd in res:
       if not cmd.ok:
          print(f"{cmd.command} failed")
          continue

       # do something with cmd.output as dict since ofmt was 'json'
```
