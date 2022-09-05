from threading import Thread
import time
from types import NoneType

class DBConnectionError(Exception):
    '''
    Occurs when the connection with the db fails
    
    Attributes
    ----------
    args : tuple
        arguments of the exception that led to this error
    '''
    def __init__(self, e):
        self.args = e.args

class DBWritingError(Exception):
    '''
    Occurs when the writing to the db fails

    Attributes
    ----------
    args : tuple
        arguments of the exception that led to this error
    '''
    def __init__(self, e):
        self.args = e.args

class DBNoDataReceivedError(Exception):
    '''Occurs when a query doesn't return any data'''
    def __init__(self):
        pass

class DBTimeoutError(Exception):
    '''Occurs when the database doesn't respond'''
    def __init__(self):
        pass

class ApiConnectionError(Exception):
    '''
    Occurs when the connection with an api fails
    
    Attributes
    ----------
    args : tuple
        arguments of the exception that led to this error
    '''
    def __init__(self, e):
        self.args = e.args

class DataIncompleteError(Exception):
    '''
    Occurs when the data of an api request is incomplete
    
    Attributes
    ----------
    missing : list
        keys of the missing values in the response
    '''
    def __init__(self):
        self.missing = []

class WStOfflineError(Exception):
    '''
    Occurs when the data of a request is outdated
    
    Attributes
    ----------
    t : datetime
        moment when the api values were last updated
    '''
    def __init__(self, t):
        self.last_online = t

class ApiTimeoutError(Exception):
    '''Occurs when the api doesn't respond'''
    def __init__(self):
        pass

class TimeoutHelper(Thread):
    '''
    A helper class for the measurement of timeouts

    The function that should have the timeout gets defined and handed over to the 
    constructor of this class. This function has to return two values. The first 
    has to be True or the returned value of the defined function and the second 
    Value has to be false or the error the defined function raises.
    Then the timer() method of this class is called with the length of the timeout 
    in milliseconds and the Error that should be called when the timeout occurs.
    e.g.:
            def func():
                try:
                    self.con.ping(reconnect=True)
                    return True, None
                except pymysql.err.OperationalError as e:
                    return None, DBConnectionError(e)
            timeout = TimeoutHelper(ping)
            timeout.timer(self.config['timeoutMs'], DBTimeoutError)
    
    The timer() method will return the first value returned from the defined function
    if it is not None of False and raise the second value like an exception. 
    It will also raise the given error when the defined time is over.

    Attributes
    ----------
    daemon : bool
        is true and makes the thread a daemon
    func : function
        the function given to the constructor
    r : any
        the value that gets returned by timer()
    e : Exception
        the exception that gets raised by timer()

    Methods
    -------
    run():
        Overwritten method that gets executed in the thread.
    timer():
        Handles the extra thread and measures the timeout.
    '''
    def __init__(self, func):
        Thread.__init__(self)
        self.daemon=True
        self.func = func
        self.r = None # values that are returned from func
        self.e = None # errors from func

    def run(self):
        '''Call the given func.'''
        self.r, self.e = self.func()

    def timer(self, timeout, timeout_error):
        '''
        Starts the thread and measures the time for the timeout.
        
        Returns the first returned value of func and raises the second value
        as an exception.

                Parameters:
                        timeout (int) : Timeout length in milliseconds.
                        timeout_error (Exception) : Exception that gets raised when 
                            the timeout is exceeded.
        '''
        self.start()
        t = timeout
        while t > 0:
            if self.e:
                raise self.e
            elif type(self.r) is not NoneType:
                return self.r
            else:
                time.sleep(0.001)
                t -= 1
        else:
            raise timeout_error
