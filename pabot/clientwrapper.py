import sys

try:
    from .py3.client import make_order
except SyntaxError:

    def make_order(*args):
        print("Client needs to be run in Python >= 3.6")
        print("You are running %s" % sys.version)
        sys.exit(1)
