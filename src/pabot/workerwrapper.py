import sys

try:
    from .py3.worker import main
except SyntaxError:
    print("Worker needs to be run in Python >= 3.6")
    print("You are running %s" % sys.version)
    sys.exit(1)
