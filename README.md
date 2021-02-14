# Auto-XDCC downloader for Hexchat

Automated downloader using XDCC in Hexchat, geared towards anime and music bots and their packlists.

## Requirements

- Hexchat >= 2.10 with Python plugin
- Python >= 3.5
  - [requests](https://pypi.org/project/requests/) >= 2.10

## Install

All the requirements above should be installed first before attempting to install the addon.

### Automatic

Scripts are available for both Linux and Windows.
To run the install:

```
$ bin/deploy.sh
> bin\deploy.bat
```

If your **Linux** distro's config path differs from `~/.config/hexchat` or **Windows's** `%APPDATA%\HexChat`,
specify the path as argument to the script

```
$ bin/deploy.sh /path/to/hexchat/config
> bin/deploy.bat C:\path\to\hexchat\config
```

### Manual

- Copy all files from src/ to your Hexchat config's `addons` subfolder
- If it's a new install, copy `config/xdcc_store.json` to the same folder. Otherwise it's suggested to run `tools/store_convert.py` to convert from older store versions to the latest version.
