import sys
try:
    from .py3.coordinator import main
except SyntaxError:
    print("Coordinator needs to be run in Python >= 3.6")
    print("You are running %s" % sys.version)
    sys.exit(1)