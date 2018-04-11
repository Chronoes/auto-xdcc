"""
Wrapper for Python's argparse module
"""

import argparse as _argparse
import sys as _sys

class ArgumentParser(_argparse.ArgumentParser):
    def _print_message(self, message, file=None):
        # Allow messages only in stdout
        if message:
            _sys.stdout.write(message)

    def exit(self, status=0, message=None):
        # Prevent exit command from performing sys.exit
        self._print_message(message)
        raise Exception(message)
