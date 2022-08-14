
from ast import Return
from threading import Thread
import time

class DBConnectionError(Exception):
    def __init__(self, e):
        self.args = e.args

class DBWritingError(Exception):
    def __init__(self, e):
        self.args = e.args

class DBTimeoutError(Exception):
    def __init__(self):
        pass

class ApiConnectionError(Exception):
    def __init__(self, e):
        self.args = e.args

class DataIncompleteError(Exception):
    def __init__(self):
        self.missing = []

class WStOfflineError(Exception):
    def __init__(self, t):
        self.last_online = t

class ApiTimeoutError(Exception):
    def __init__(self):
        pass

class TimeoutHelper(Thread):
    def __init__(self, func):
        Thread.__init__(self)
        self.func = func
        self.r = None # values that are returned from func
        self.e = None # errors from func

    def run(self):
        # call func
        self.r, self.e = self.func()

    def timer(self, timeout, timeout_error):
        # timeout measurement
        self.start()
        t = timeout
        while t > 0:
            if self.e:
                raise self.e
            elif self.r:
                return self.r
            else:
                time.sleep(0.001)
                t -= 1
        else:
            raise timeout_error
