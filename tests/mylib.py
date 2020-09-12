class mylib(object):
    ROBOT_LIBRARY_SCOPE = "TEST"

    def __init__(self):
        self.round = 0

    def mykeyword(self):
        self.round += 1
        return "hello world %s" % self.round
