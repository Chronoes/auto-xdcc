#!/usr/bin/bash
VERSION=$1
cd /home/hexchat

if [ -f .config/hexchat/addons/auto_xdcc.py ]; then
    current_version=`cat .config/hexchat/addons/auto_xdcc.py | grep '__module_version__' | grep -oE '([0-9]+\.)+[0-9]+'`
    # VERSION <= current_version
    if [ "$VERSION" = "`echo -e "$VERSION\n$current_version" | sort -V | head -n1`" ]; then
        echo "Current plugin version $current_version is up-to-date"
        exit 0
    fi
fi

echo "Installing plugin version v$VERSION"
mkdir plugin
cd plugin

wget https://github.com/Chronoes/auto-xdcc/archive/refs/tags/v$VERSION.tar.gz
if [ ! $? ]; then
    echo "Failed to fetch plugin v$VERSION"
    exit 1
fi

tar xvzf v$VERSION.tar.gz
cd auto-xdcc-$VERSION
bin/deploy.sh /home/hexchat/.config/hexchat
cd /home/hexchat
rm -r plugin
