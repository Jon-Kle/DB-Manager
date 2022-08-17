from queue import Queue
from threading import Thread


class Printer(Thread):
    '''
    A class that queues all messages printed and prints them in order
    
    Attributes
    ----------
    queue : queue
        the queue where the messages for printing are stored
    daemon : bool
        determines that this thread is a daemon

    Methods
    -------
    run():
        Function that gets executed by the thread.
        Prints the contents of queue continuously.
    print(str):
        Function for adding a string to the queue and thus printing it.
    '''

    def __init__(self):
        Thread.__init__(self)
        self.queue = Queue()
        self.name = 'Printer'
        self.daemon = True
        self.start()

    def run(self):
        '''Run indefinitely and try to print the contents of queue'''
        while True:
            msg, end = self.queue.get()
            print(msg, end=end)

    def print(self, msg, end='\n'):
        '''Add a string to queue'''
        self.queue.put((msg, end))