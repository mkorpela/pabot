class mylib(object):
    ROBOT_LIBRARY_SCOPE = "TEST"

    def __init__(self, round=0):
        self.round = round

    def mykeyword(self):
        self.round += 1
        return "hello world %s" % self.round
