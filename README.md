# Arista EOS API asyncio Client

This repository contains an Arista EOS asyncio client.

### Quick Example

This following shows how to create a Device instance and run a list of
commands.

Device will use HTTPS transport by default. The Device instance supports the
following initialization parameters:

- `host` - The device hostname or IP address
- `username` - The login username
- `password` - The login password
- `proto` - _(Optional)_ Choose either "https" or "http", defaults to "https"
- `port` - _(Optional)_ Chose the protocol port to override proto default

The Device class inherits directly from httpx.AsyncClient. As such, the Caller
can provide any initialization parameters. The above specific parameters are
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

### References

Arista eAPI documents require an Arista Portal customer login. Once logged into the
system you can find the documents in the Software Download area. Select an EOS release
and then select the Docs folder.

You can also take a look at the Arista community client, [here](https://github.com/arista-eosplus/pyeapi).
