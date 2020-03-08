import sys
try:
    from .coordinator import main
except SyntaxError:
    print("Coordinator needs to be run in Python 3")
    print("You are running %s" % sys.version)
    sys.exit(1)