# Auto-XDCC downloader for Hexchat

Automated downloader using XDCC in Hexchat, geared towards anime and music bots and their packlists.

## Requirements

* Hexchat >= 2.10 with Python plugin
* Python >= 3.5
  * [requests](https://pypi.org/project/requests/) >= 2.10

## Install

All the requirements above should be installed first before attempting to install the addon.

### Automatic

Currently available only for Linux as a Shell script. Also works in Windows Subsystem for Linux (WSL).

Make sure `bin/deploy.sh` and `tools/store_convert.py` have executable rights.

To run the install:

`$ bin/deploy.sh`

If your **Linux** distro's config path differs from `~/.config/hexchat`, make sure `HEXCHAT_CONF` environment variable is available.

`$ HEXCHAT_CONF=/path/to/hexchat/config bin/deploy.sh`

The same applies for **WSL**. It will look something like this:

`$ HEXCHAT_CONF=/mnt/c/Users/user/AppData/Roaming/HexChat bin/deploy.sh`

### Manual

* Copy all files from src/ to your Hexchat config's `addons` subfolder
* If it's a new install, copy `config/xdcc_store.json` to the same folder. Otherwise it's suggested to run `tools/store_convert.py` to convert from older store versions to the latest version.
