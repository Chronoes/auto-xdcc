FROM archlinux
RUN pacman -Syu --noconfirm hexchat python python-cffi python-requests tmux wget
RUN wget -O /usr/local/bin/dumb-init https://github.com/Yelp/dumb-init/releases/download/v1.2.5/dumb-init_1.2.5_x86_64
RUN chmod +x /usr/local/bin/dumb-init
VOLUME [ "/home/hexchat/downloads", "/home/hexchat/.config/hexchat" ]

ADD container/bootstrap.sh /bootstrap.sh
ADD container/init /init
ADD container/home /home/hexchat
RUN chmod +x /init /bootstrap.sh
ENTRYPOINT [ "/usr/local/bin/dumb-init", "--" ]
CMD [ "/init" ]
