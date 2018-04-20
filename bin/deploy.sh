#!/bin/sh
# Deploys the addon for Hexchat.
# Specify HEXCHAT_CONF env variable if config path differs from default: $HOME/.config/hexchat

hexchat_path="${HEXCHAT_CONF:-$HOME/.config/hexchat}"

[ ! -d "$hexchat_path" ] \
    && echo "Is Hexchat installed? Is Hexchat config located at $hexchat_path?" \
    && echo "If config is elsewhere, specify HEXCHAT_CONF env variable to this script to change the location" \
    && exit 1

mkdir -p "$hexchat_path/addons"

root_folder="$(dirname $0)/.."

if [ -f "$hexchat_path/addons/xdcc_store.json" ]; then
    "$root_folder/tools/store_convert.py" "$hexchat_path/addons/xdcc_store.json" -o "$hexchat_path/addons/xdcc_store.json" \
    && echo "Config file updated." \
    || (echo "Config update failed." && exit 2)
else
    cp "$root_folder/config/xdcc_store.json" "$hexchat_path/addons"
    echo "New config file created."
fi

cp -r "$root_folder/src" "$hexchat_path/addons"

echo "Auto-XDCC installed."
echo "Restart Hexchat or type /py load auto_xdcc.py or /py reload auto_xdcc.py to get it working."
