# AXDCC Docker

Docker image to run Hexchat with AXDCC installed.

## Preparing config

Before building, it is advisable to review the [hexchat config](container/home/.config/hexchat).
**hexchat.conf** contains Hexchat config and it is imperative to have an unique name for your bot:
```
irc_nick1 = RoBotNick
irc_nick2 = RoBotNick2
irc_nick3 = RoBotNick3
```

**servlist.conf** is used for auto-connecting to the desired server(s) and channel(s) if necessary.

## Building image

```bash
docker build -t axdcc:latest .
```

## Creating container

It is recommended to use Docker Compose.
Make changes to **docker-compose.yml** to suit your host environment.

Environment:
- HEXUID - UID on host volumes
- HEXGID - GID on host volumes
- VERSION - Version of AXDCC plugin

Volumes:
- Hexchat config folder
  - /home/hexchat/.config/hexchat
- Hexchat downloads folder
  - /home/hexchat/downloads

## Running container with Docker Compose

Container can simply be started as usual
```bash
docker-compose up -d
```

If you need to access the Hexchat instance directly, attach to the running container's `tmux` session.
```bash
docker exec -ti -u hexchat axdcc /usr/bin/tmux attach
```
Make sure you exit by detaching from `tmux` by typing Ctrl+b and d, otherwise it will not work.
