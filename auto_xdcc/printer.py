import hexchat

def get_context():
    server_name = hexchat.get_info('server')
    return hexchat.find_context(channel=server_name)

def _print(line, prefix="26»28»"):
    srv = get_context()
    prefixed_line = "{} Auto-XDCC: {}".format(prefix, line)
    if srv:
        srv.prnt(prefixed_line)
    else:
        print(prefixed_line)

def x(line):
    _print(line)

def info(line):
    _print("INFO - " + str(line), "29»22»")

def error(line):
    _print("Error - " + str(line), "18»18»")
