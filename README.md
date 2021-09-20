# Arista EOS API asyncio Client

This repository contains an Arista EOS asyncio client.

### Quick Example

Thie following shows how to create a Device instance and run a list of
commands.

Device will use HTTPS transport by default.  The Device instance supports the
following initialization parameters:

   * `host` - The device hostname or IP address
   * `username` - The login username
   * `password` - The login password
   * `proto` - *(Optional)* Choose either "https" or "http", defaults to "https"
   * `port` - *(Optional)* Chose the protocol port to override proto default

The Device class inherits directly from httpx.AsyncClient.  As such, the Caller
can provide any initialization parameters.  The above specific parameters are
all optional.

```python
import json
from aioeapi import Device

username = 'dummy-user'
password = 'dummy-password'

async def run_test(host):
    dev = Device(host=host, username=username, password=password)
    res = await dev.cli(commands=['show hostname', 'show version'])
    json.dumps(res)
```
