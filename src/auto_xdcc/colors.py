from enum import Enum


class ControlChars(Enum):  # from https://hexchat.readthedocs.io/en/latest/script_python.html#text-formatting and https://github.com/hexchat/hexchat/blob/master/src/fe-gtk/xtext.h
    bold = ""       # 	'\002' OCTAL!!!
    color = ""      # 	'\003'
    blink = ""      #  '\006'
    beep = ""       #  '\007'
    hidden = ""     #  '\010'
    italics_old = "	" #  '\011'  # old italics, since its an invisible unicode char, its "Horizontal Tab"
    reset = ""      #  '\017'
    reverse = ""    #  '\026' # reverse Color, 
    italics = ""    #  '\035' # available since 2.10.0+
    strikethrough = ""  # '\036' # available since 2.16.0+
    underline = ""  #  '\037'


class Color(Enum):  # taken from https://github.com/hexchat/hexchat/blob/master/src/fe-gtk/palette.c
    white = 0
    black = 1
    blue = 2
    green = 3
    red = 4
    light_red = 5
    purple = 6
    orange = 7
    yellow = 8
    light_green = 9
    aqua = 10
    light_aqua = 11
    blue_grey = 12
    light_purple = 13
    grey = 14
    light_grey = 15
    white2 = 16
    black2 = 17
    blue2 = 18
    green2 = 19
    red2 = 20
    light_red2 = 21
    purple2 = 22
    orange2 = 23
    yellow2 = 24
    light_green2 = 25
    aqua2 = 26
    light_aqua2 = 27
    blue_grey2 = 28
    light_purple2 = 29
    grey2 = 30
    light_grey2 = 31


def get_color(color):
    if type(color) == Color:
        return ControlChars.color.value + str(color.value)
    else:
        raise Exception("Color not valid!")
