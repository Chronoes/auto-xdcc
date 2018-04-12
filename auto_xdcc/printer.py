import hexchat

def _get_context():
    server_name = hexchat.get_info('server')
    return hexchat.find_context(channel=server_name)

def _print(line):
    srv = _get_context()
    if srv:
        srv.prnt(line)
    else:
        print(line)

def x(line):
    _print("26»28» Auto-XDCC: " + str(line))

def info(line):
    _print("29»22» Auto-XDCC: INFO - " + str(line))

def error(line):
    _print("18»18» Auto-XDCC: Error - " + str(line))

def list(line):
    _print(" 18» " + str(line))
