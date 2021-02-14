"""
Wrapper for Python's argparse module
"""

import argparse as _argparse
import sys as _sys

class ArgumentParser(_argparse.ArgumentParser):
    def __init__(self, printer=None, **kwargs):
        self.printer = printer
        super().__init__(**kwargs)

    def _print_message(self, message, file=None):
        # Allow messages only in configured printer
        if message:
            self.printer.error(message)

    def exit(self, status=0, message=None):
        # Prevent exit command from performing sys.exit
        self._print_message(message)
        raise Exception(message)

    def error(self, message):
        # Prevent error command from performing sys.exit
        raise Exception(message)
