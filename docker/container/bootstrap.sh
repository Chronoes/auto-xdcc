#!/usr/bin/bash

HEXUID=${HEXUID:-1000}
HEXGID=${HEXGID:-1000}

echo "Creating user hexchat with $HEXUID:$HEXGID"
groupadd --non-unique --gid $HEXGID hexchat
useradd --non-unique --no-create-home --home-dir /home/hexchat --uid $HEXUID --gid $HEXGID hexchat
cd /home/hexchat

echo 'Creating required folders'
mkdir --parents downloads/completed .config/hexchat/addons
if [ ! -f .config/hexchat/hexchat.conf ]; then
    echo 'Initializing Hexchat config'
    cp -r --verbose .config/hexchat-default/. .config/hexchat
fi
chown hexchat:hexchat -R .

echo 'Bootstrap complete'
