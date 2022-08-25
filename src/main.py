from customExceptions import * # custom exceptions and TimeoutHelper
import sys, os, time # System
from datetime import datetime, timedelta # for names of request files and RequestTimer
import email.utils # for conversion of rfc822 to datetime
from threading import Thread # For RequestTimer
import hmac # Hash function for WeatherLink-API
import pymysql, requests, json # APIs and database
import cmd, readline # Command line
import csv # Read download-files

class TimeUtils:
    '''
    Class to help with datetime objects and handle the timing of request

    Methods
    -------
    get_now():
            returns datetime object of CET timezone
    get_next_req_time():
            Calculates next_req.
    '''

    def get_now(self, string=False):
        '''
        Return a naive datetime object of the CET zone

                parameters:
                        string (bool) : lets this method return a string of
                            the datetime object in iso format.
        '''
        now = datetime.utcnow() + timedelta(hours=1)  # uses CET, ignores DTS
        now = now.replace(microsecond=0)
        if string:
            return now.isoformat(sep=' ')
        return now

    def get_next(self, now=None):
        '''
        Calculate time of next request.

        is always at xx:00 or at xx:30

                parameters:
                        now (datetime) : starting point for calculation.
                            If None the current time in CET gets used.
        '''
        if not now:
            now = self.get_now()
        next_req = now + timedelta(minutes=30)
        minutes = next_req.minute
        if minutes < 30:
            next_req = next_req.replace(minute=0, second=0, microsecond=0)
        else:
            next_req = next_req.replace(minute=30, second=0, microsecond=0)
        return next_req

class Configuration:
    '''
    A Class to read and save the config.json file.

    Attributes
    ----------
    data : dict
            content of the config.json file

    Methods
    -------
    save():
            Writes the loaded data into the config.json file.
    '''

    def __init__(self):
        '''Open the config.json file and save its content in the attribute "data"'''
        self.data = None
        self.excluded = []
        # load config file
        f = open('../rsc/config.json')
        s = f.read()
        self.data = json.loads(s)
        f.close()
        # load dat file
        f = open('../rsc/dat.json')
        s = f.read()
        self.secrets = json.loads(s)

        # check for empty values
        for k in self.data.keys():
            for k2 in self.data[k].keys():
                if self.data[k][k2] == '':
                    self.data[k][k2] = self.secrets[k][k2]
                    self.excluded.append((k, k2))

    def save(self):
        '''Save the content of "data" in the config.json file.'''
        # remove excluded data
        for e in self.excluded:
            k, k2 = e[0], e[1]
            self.secrets[k][k2] = self.data[k][k2]
            self.data[k][k2] = ''

        # save config file
        configFile = open('../rsc/config.json', 'w')
        json.dump(self.data, configFile, indent='\t')
        configFile.close()
        # save dat file
        datFile = open('../rsc/dat.json', 'w')
        json.dump(self.secrets, datFile, indent='\t')
        configFile.close()

class Database:
    '''
    A class to represent the MySQL Database.

    Attributes
    ----------
    config : dict
            configuration data for the database connection
    con : pymysql.connection
            connection object of pymysql
            This is None, if the connection is not established.
    cursor : pymysql.cursors.DictCursor
            cursor object for database

    Methods
    -------
    check():
            calls connect() and checks if writing to the db is possible
    connect():
            tries to establish the connection with the db
    ping():
            checks the connection with a ping and reconnects if necessary
    add_row(values):
            adds a line at the end of the db with the data from "values"
    rm_last():
            removes the last entry
    check_writing_to_db():
            Writes and deleted one line to the database
            to check if writing to the db is possible.
    '''

    def __init__(self):
        self.config = config.data['db']
        self.entries = []
        self.gaps = []

    def check(self):
        '''
        Establish a connection and check if writing works.

                Exceptions:
                        DBConnectionError
                        DBWritingError
                        DBTimeoutError
        '''
        self.connect()
        self.check_writing_to_db()

    def connect(self):
        '''
        Try to connect with the mysql database.

                Exceptions:
                    DBConnectionError
                    DBTimeoutError
        '''
        self.con = None
        self.cursor = None
        # this function gets executed in another thread
        def con():
            try:
                c = pymysql.connect(
                    port=self.config['port'],
                    host=self.config['host'],
                    user=self.config['user'],
                    password=self.config['password'],
                    database=self.config['database'],
                    cursorclass=pymysql.cursors.DictCursor)
                return c, None
            except pymysql.err.OperationalError as e:
                return None, DBConnectionError(e)
        timeout = TimeoutHelper(con)
        # this starts the thread with con() and a timer
        # finishes the timer before the function is executed, a timeout error is raised
        self.con = timeout.timer(self.config['timeoutMs'], DBTimeoutError)
        self.cursor = self.con.cursor()

    def ping(self):
        '''
        Check the connection and (re-)connect if necessary.

                Exceptions:
                    DBConnectionError
                    DBTimeoutError
        '''
        if not self.con:
            self.connect()
        # add timeout
        def ping():
            try:
                self.con.ping(reconnect=True)
                return True, None
            except pymysql.err.OperationalError as e:
                return None, DBConnectionError(e)
        timeout = TimeoutHelper(ping)
        timeout.timer(self.config['timeoutMs'], DBTimeoutError)

    def add_row(self, values):
        '''
        Add a row to the db with the values from "values".

                Parameters:
                        values (list) : Values that get written into the db

                Exceptions:
                        DBWritingError
                        DBTimeoutError
        '''
        queryString = f"INSERT INTO `weatherdata` (`entryDate`, `temp`, `pressure`, `hum`, `windspeed`, `winddir`, `rainrate`, `uvindex`)\
 VALUES ('{values[0]}', '{values[1]}', '{values[2]}', '{values[3]}', '{values[4]}', '{values[5]}', '{values[6]}', '{values[7]}');"
        # this function gets executed in another thread
        def exec():
            try:
                self.cursor.execute(queryString)
                self.con.commit()
                return True, None
            except pymysql.Error as e:
                return None, DBWritingError(e)
            except AttributeError as e:
                return None, DBConnectionError(e)
        timeout = TimeoutHelper(exec)
        # this starts the thread with con() and a timer
        # finishes the timer before the function is executed, a timeout error is raised
        timeout.timer(self.config['timeoutMs'], DBTimeoutError)

    def rm_last(self):
        '''
        Remove last row in the "weatherdata" table.

                Exceptions:
                        DBWritingError
                        DBTimeoutError
        '''
        def exec():
            try:
                self.cursor.execute(
                    "DELETE FROM `weatherdata` WHERE -1 ORDER BY entryDate DESC LIMIT 1;")
                self.con.commit()
                return True, None
            except pymysql.Error as e:
                return None, DBWritingError(e)
        timeout = TimeoutHelper(exec)
        # this starts the thread with con() and a timer
        # finishes the timer before the function is executed, a timeout error is raised
        timeout.timer(self.config['timeoutMs'], DBTimeoutError)

    def check_writing_to_db(self):
        '''
        Check if writing to the db is possible by adding and removing one line to the db.

            Exceptions:
                    DBWritingError
                    DBTimeoutError
        '''
        def exec():
            try:
                self.cursor.execute(f"INSERT INTO `weatherdata` (`entryDate`, `temp`, `pressure`, `hum`, `windspeed`, `winddir`, `rainrate`, `uvindex`)\
 VALUES ('0000-01-01 00:00:00', '26.9', '1014.7', '39', '1.60934', 'SO', '0.0', '2.2');")
                self.cursor.execute("DELETE FROM `weatherdata` WHERE entryDate = '0000-01-01 00:00:00';")
                self.con.commit()
                return True, None
            except pymysql.Error as e:
                return None, DBWritingError(e)
        timeout = TimeoutHelper(exec)
        timeout.timer(self.config['timeoutMs'], DBTimeoutError)

    def get_entries(self):
        def get_data():
            try:
                db.cursor.execute('SELECT entryDate FROM weatherdata') # WHERE entryDate >= "2022-08-24 09:47:08"
                data = db.cursor.fetchall()
                if len(data) == 0:
                    return [], None
                return data, None
            except AttributeError as e:
                return None, DBConnectionError(e)
        timeout = TimeoutHelper(get_data)
        data = timeout.timer(self.config['timeoutMs'], DBTimeoutError)
        if data == []:
            return

        data = [e['entryDate'] for e in data]
        entries = []
        first_str = self.config["mendStartTime"]
        first_l = first_str.split(sep=",")
        first = datetime(*[int(s) for s in first_l])
        last = time_utils.get_next()

        current = first
        while current != last:
            if current in data:
                entries.append((current, True))
            else:
                entries.append((current, False))
            current += timedelta(minutes=30)
        self.entries = entries
        return entries

    def get_gaps(self):
        last_status = True
        gaps = []
        for i in self.entries:
            if not i[1] and last_status:
                start = i[0]
                count = 1
            elif not i[1] and not last_status:
                count += 1
            elif i[1] and not last_status:
                end = i[0]
                gaps.append((start, end, count))
            last_status = i[1]
        print(*gaps, sep="\n")
        self.gaps = gaps

class Api1:
    '''
    A class to represent the WeatherLink API V1

    This API is very simple. It takes over all credentials directly without any
    security measures, except for the HTTPS protocol.

    API documentation: https://www.weatherlink.com/static/docs/APIdocumentation.pdf

    Attributes
    ----------
    config : dict
            configuration data from which url, user, password and token are extracted
    url : str
            the URL that is used for the request
    user : str
            device-ID (DID) of the Data Logger mounted to the console of the station
    password : str
            the password that is also used to log into the WeatherLink website
    token : str
            unique API-Token. don't share with anyone!
            If compromised generate a new one at https://www.weatherlink.com/account

    Methods
    -------
    check():
            Check if connection works and if the data is complete and up to date.
    request():
            Makes an HTTP request with the given values.
            Returns the answer in json format as a dict.
    get_values():
            Extracts the Values for the db from a request and returns them.
    '''

    def __init__(self):
        self.config = config.data['Api1']
        self.url = self.config['url']
        self.user = self.config['user']
        self.password = self.config['pass']
        self.token = self.config['apiToken']

    def check(self):
        '''
        Check if the connection works, the data complete and is up to date.

                Exceptions:
                        ApiConnectionError
                        DataIncompleteError
                        WStOfflineError
                        ApiTimeoutError
        '''
        self.get_values()

    def request(self):
        '''
        Return response from the Api as a dict.

                Exceptions:
                        ApiConnectionError
                        ApiTimeoutError
        '''
        ans = None
        payload = {
            'user': self.user,
            'pass': self.password,
            'apiToken': self.token
        }
        # this function gets executed in another thread
        def req():
            try:
                r = requests.get(self.url, params=payload)
                return r, None
            except requests.ConnectionError as e:
                return None, ApiConnectionError(e)
        timeout = TimeoutHelper(req)
        # this starts the thread with req() and a timer
        # finishes the timer before the function is executed, a timeout error is raised
        r = timeout.timer(self.config['timeoutMs'], ApiTimeoutError)

        return r.json()  # parses dict of json response

    def get_values(self, time=None):
        '''Make API1 Request and get selected values to form a list.

                Parameters:
                        time (str) : overwrites the entryDate value in vlist

                Exceptions:
                        ApiConnectionError
                        DataIncompleteError
                        WStOfflineError
                        ApiTimeoutError
        '''
        if not time:
            time = time_utils.get_now(string=True)
        # request Api1
        data = self.request()

        # check if data is up to date
        datestr = data['observation_time_rfc822']
        datet = email.utils.parsedate_to_datetime(datestr)
        datet = datet.replace(tzinfo=None)-timedelta(hours=1)
        now = time_utils.get_now()
        deltat = now - datet
        if deltat > timedelta(minutes= self.config['dataMaxAge']):
            raise WStOfflineError(datet)

        vlist = {}
        # date
        vlist['time'] = time

        self.error = None
        def handler():
            if self.error == None:
                self.error = DataIncompleteError()
            self.error.missing.append(e.args[0])
        try:
            # temp
            vlist['temp'] = data['temp_c']
        except KeyError as e:
            handler()
        try:
            # pressure
            vlist['pressure'] = data['pressure_mb']
        except KeyError as e:
            handler()
        try:
            # hum
            vlist['hum'] = data['relative_humidity']
        except KeyError as e:
            handler()
        try:
            # wind_speed
            in_kmh = float(data['wind_mph'])
            in_kmh *= 1.60934
            vlist['wind_speed'] = str(in_kmh)
        except KeyError as e:
            handler()
        try:
            # wind_dir
            w_dir = int(data['wind_degrees'])
            w_dir_str = None
            if w_dir >= 349 or w_dir <= 11:
                w_dir_str = 'N'
            elif w_dir >= 12 and w_dir <= 33:
                w_dir_str = 'NNO'
            elif w_dir >= 34 and w_dir <= 56:
                w_dir_str = 'NO'
            elif w_dir >= 57 and w_dir <= 78:
                w_dir_str = 'ONO'
            elif w_dir >= 79 and w_dir <= 101:
                w_dir_str = 'O'
            elif w_dir >= 102 and w_dir <= 123:
                w_dir_str = 'OSO'
            elif w_dir >= 124 and w_dir <= 146:
                w_dir_str = 'SO'
            elif w_dir >= 147 and w_dir <= 168:
                w_dir_str = 'SSO'
            elif w_dir >= 169 and w_dir <= 191:
                w_dir_str = 'S'
            elif w_dir >= 192 and w_dir <= 213:
                w_dir_str = 'SSW'
            elif w_dir >= 214 and w_dir <= 236:
                w_dir_str = 'SW'
            elif w_dir >= 237 and w_dir <= 258:
                w_dir_str = 'WSW'
            elif w_dir >= 259 and w_dir <= 281:
                w_dir_str = 'W'
            elif w_dir >= 282 and w_dir <= 303:
                w_dir_str = 'WNW'
            elif w_dir >= 304 and w_dir <= 326:
                w_dir_str = 'NW'
            elif w_dir >= 327 and w_dir <= 348:
                w_dir_str = 'NNW'
            vlist['wind_dir'] = w_dir_str
        except KeyError as e:
            handler()
        try:
            # rain_rate_per_hr
            in_mm = float(data['davis_current_observation']
                      ['rain_rate_in_per_hr']) * 25.4
            vlist['rain_rate_per_hr'] = str(in_mm)
        except KeyError as e:
            handler()
        try:
            # uv_index
            vlist['uv_index'] = data['davis_current_observation']['uv_index']
        except KeyError as e:
            handler()

        if self.error: raise self.error

        return list(vlist.values())

class Api2:
    '''
    A class to represent the API V2 (Not actively used!)

    This API is more complex than the API V1.
    It is more sophisticated and uses an HMAC algorithm with sha256 for more security

    API documentation: https://weatherlink.github.io/v2-api/

    Attributes
    ----------
    config : dict
            configuration data from which url, key, secret and station_id are extracted
    url : str
            the URL that is used for the request
    key : str
            used to identify the user making the request
    secret : str
            used to calculate the signature for the request don't share with anyone!
            If compromised generate a new one at https://www.weatherlink.com/account
    station_id : str
            ID which identifies the weather station the data is requested from

    Methods
    -------
    check():
            Checks the connection with the Api
    request():
            Makes an HTTP request with the values and the calculated signature.
    get_stations():
            Makes an HTTP request to get all the possible station IDs and returns the answer in a compact format.
    '''

    def __init__(self):
        self.config = config.data['Api2']
        self.url = self.config['url']
        self.key = self.config['api-key']
        self.secret = self.config['api-secret']
        self.station_id = self.config['stationID']

    def check(self):
        '''
        Check the connection with the Api.

                Exceptions:
                        ApiConnectionError
                        ApiTimeoutError
        '''
        self.request()

    def request(self):
        '''
        Return dict from Api2 http request.

                Exceptions:
                        ApiConnectionError
                        ApiTimeoutError
        '''
        t = int(time.time())
        param_str = f'api-key{self.key}station-id{self.station_id}t{t}'
        hmac_obj = hmac.new(str.encode(self.secret),
                            str.encode(param_str), 'sha256')
        api_signature = hmac_obj.hexdigest()

        payload = {
            'api-key': self.key,
            't': t,
            'api-signature': api_signature
        }
        # this function gets executed in another thread
        def req():
            try:
                r = requests.get(self.url + 'current/' +
                                 self.station_id + '?', params=payload)
                return r, None
            except requests.ConnectionError as e:
                return None, ApiConnectionError(e)
        timeout = TimeoutHelper(req)
        # this starts the thread with req() and a timer
        # finishes the timer before the function is executed, a timeout error is raised
        r = timeout.timer(self.config['timeoutMs'], ApiTimeoutError)

        return r.json()  # parses dict of json response

    def get_stations(self):
        '''
        Return IDs and names from weatherlink Stations as dict

                Exceptions:
                        ApiConnectionError
                        ApiTimeoutError
        '''
        t = int(time.time())
        param_str = f'api-key{self.key}t{t}'
        hmac_obj = hmac.new(str.encode(self.secret),
                            str.encode(param_str), 'sha256')
        api_signature = hmac_obj.hexdigest()

        payload = {
            'api-key': self.key,
            't': t,
            'api-signature': api_signature
        }
        # this function gets executed in another thread
        def req():
            try:
                r = requests.get(self.url + 'stations?', params=payload)
                return r, None
            except requests.ConnectionError as e:
                return None, ApiConnectionError(e)
        timeout = TimeoutHelper(req)
        # this starts the thread with req() and a timer
        # finishes the timer before the function is executed, a timeout error is raised
        r = timeout.timer(self.config['timeoutMs'], ApiTimeoutError)

        st = r.json()
        st_compact = []
        for i, e in enumerate(st['stations']):
            new_st = {'station_id': e['station_id'],
                          'station_name': e['station_name']}
            st_compact.append(new_st)
        return st_compact  # return stations as dict

class RequestTimer:
    '''
    A class that periodically loads data into the database

    Attributes
    ----------
    config : dict
            configuration data for requestTimer
    show_msg : bool
            determines if a message is shown when a line is added to the database
    next_req : datetime
            time when the next line will be added to the database
    seconds_till_next : int
            seconds till the next requests gets triggered
    thread : Thread
            thread for the timer
    run : bool
            indicates when the timer is running

    Methods
    -------
    start():
            Creates thread for the timer and starts it.
    timer():
            Counts seconds_till_next and calls make_req().
    make_req(time=None):
            Makes request and adds row to the database.
    line_msg(time, vlist):
            Builds message for when a line is added to the database
    '''

    def __init__(self):
        # configuration
        self.config = config.data['requestTimer']
        self.show_msg = self.config['show_message']
        self.run = False
        self.trigger_debug_action = False

    def start(self):
        '''Initiate thread with timer().'''
        self.next_req = time_utils.get_next()
        self.seconds_till_next = (self.next_req-time_utils.get_now()).seconds

        self.thread = Thread(name='timer', target=self.timer, daemon=True)
        self.thread.start()

    def timer(self):
        '''Time requests.'''
        i = self.seconds_till_next + 1
        self.run = True
        while self.run:
            if self.trigger_debug_action:
                self.trigger_debug_action = False
                self.make_req(time=time_utils.get_now(string=True), debug=True)
            if i > 0:
                time.sleep(1)
                i -= 1
            else:
                self.make_req()
                # calculate next request
                self.next_req = time_utils.get_next()
                self.seconds_till_next = (self.next_req-time_utils.get_now()).seconds
                i = self.seconds_till_next + 1

    def make_req(self, time=None, msg=True, debug=False):
        '''
        Get values from get_values() and add them to the database.

        Trigger message if show_msg is true.
        Calculate next_req and seconds_till_next

                Parameters:
                        time (str) : overwrites the time value for the new line
                        msg (bool) : determines if a message for the added line gets shown
                        debug (bool) : gets passed on to line_msg()
        '''
        if time == None:
            time = self.next_req.isoformat(sep=' ')

        try:
            db.ping()
        except (DBConnectionError, DBTimeoutError):
            pass

        try:
            # get Values
            values = api1.get_values(time)
        except BaseException as e:
            if isinstance(e, ApiConnectionError):
                s = f'\n--> {time} - Connection with Api1 failed!\n'
            elif isinstance(e, DataIncompleteError):
                s = f'\n--> {time} - Data of request is incomplete!\n'
                s += ' missing Data:\n'
                s += cli.print_iterable(e.missing, indent=' - ') + '\n'
            elif isinstance(e, WStOfflineError):
                s = f'\n--> {time} - Data of request is outdated!\n'
            elif isinstance(e, ApiTimeoutError):
                s = f'\n--> {time} - The request timed out!\n'
            else: raise e
            s += cli.prompt
            print(s, end='')
        else:
            try:
                # add row to db
                db.add_row(values) # try
            except BaseException as e:
                if isinstance(e, DBConnectionError):
                    s = f'\n--> {time} - Connection with db failed!\n'
                elif isinstance(e, DBWritingError):
                    s = f'\n--> {time} - Writing to db failed!\n'
                elif isinstance(e, DBTimeoutError):
                    s = f"\n--> {time} - The db didn't respond!\n"
                else: raise e
                s += cli.prompt
                print(s, end='')
            else:
                # message
                if self.show_msg and msg:
                    self.line_msg(time, values, debug=debug)

    def line_msg(self, time, values, debug=False):
        '''Build message for when a new line is added to the database.

                Parameters:
                        time (str) : string that shows when the request was made
                        vlist (list) : list with values from the request
                        debug (bool) : changes the look of the message
        '''
        if debug:
            msg = ''
        else:
            msg = '\n'
        msg += f'--> {time} - '
        for i, item in enumerate(values):
            if i > 0:
                msg += item
                if i < len(values) - 1:
                    msg += ' | '
        # message if row was successfully added
        msg += ' - successful!\n'
        if not debug:
            msg += cli.prompt
        print(msg, end='')

class CLI(cmd.Cmd):
    '''
    A class for the Command Line Interface of the program.
    Extends the class cmd.Cmd.

    Attributes
    ----------
    prompt : str
            shown in front of every new prompt

    Methods
    -------
    preeloop():
            Runs before cmdloop() starts. Shows if all parts of the program work.
    default():
            Gets executed if command is unknown.
    emptyline():
            Gets executed if empty command ('') is entered.
     --- string utilities ---
    print_iterable():
            Returns string of iterable object i depending on the type.
     --- commands ---
    do_request():
            Saves answer of API1 or API2 request as .json file in "requests/".
    do_timer():
            Starts or stops the request timer.
    do_loadDownloadFiles():
            • • • under construction • • •
    do_config():
            View and change configuration.
    do_debug():
            Provides different debug functionalities.
    do_restart():
            Restart program and keep the cmd history.
    do_quit():
            Exit program.
    '''
    prompt = '---(DB-Manager)> '

    def preloop(self):
        '''Check if different parts of the program are working and build intro message.'''

        s = '    -- DB-Manager --'
        print(s)

        start_req_timer = True

        # api1
        global api1
        api1 = Api1()
        s = '\n API1 request:'
        try:
            api1.check()
        except BaseException as e:
            # msg in chat
            s += ' failed!\n'
            if isinstance(e, ApiConnectionError):
                s += '  Connection could not be established!\n'
                s += '  Make sure, the connection to the internet is working.\n'
                s += '  It could also be that the API is offline.\n\n'
            elif isinstance(e, DataIncompleteError):
                s += '  Some data values are missing:\n'
                s += self.print_iterable(e.missing, indent='  - ')
                s += '  Make sure, the wires to the different sensors are properly connected!\n\n'
            elif isinstance(e, WStOfflineError):
                s += '  The data is outdated!\n'
                s += f'  - {e.last_online.isoformat(sep=" ")}\n'
                s += '  Make sure, the weather-station is connected to the internet!\n\n'
            elif isinstance(e, ApiTimeoutError):
                s += '  The Api1 request timed out!\n'
                s += '  Make sure the connection to the internet is good.\n\n'
            else:
                raise e
            start_req_timer = False
        else:
            # msg in chat that all is well
            s += ' successful\n\n'
        print(s, end='')

        # api2 (not used)
        global api2
        s = ' API2 request:'
        try:
            api2 = Api2()
        except BaseException as e:
            # msg in chat
            s += ' failed! (not used)\n'
            if isinstance(e, ApiConnectionError):
                s += '  Connection could not be established!\n'
                s += '  Make sure, the connection to the internet is working.\n'
                s += '  It could also be that the API is offline.\n\n'
            elif isinstance(e, ApiTimeoutError):
                s += '  The Api2 request timed out!\n'
                s += '  Make sure the connection to the internet is good.\n\n'
            else:
                raise e
            start_req_timer = False
        else:
            # msg in chat that all is well
            s += ' successful\n\n'
        print(s, end='')

        # database
        global db
        db = Database()
        s = ' Connection with database:'
        try:
            db.check()
        except BaseException as e:
            # msg in chat
            s += ' failed!\n'
            if isinstance(e, DBConnectionError):
                s += f'{cli.print_iterable(config.data["db"], indent="   ")}'
                s += '  Database may not be active or the login data is incorrect!\n'
                s += '  Use "config db" to change login data and reconnect\n\n'
            elif isinstance(e, DBWritingError):
                s += ' Writing to the database raised an error:\n'
                s += str(e) + '\n\n'
            elif isinstance(e, DBTimeoutError):
                s += "  The Database didn't respond.\n"
                s += '  Maybe the Docker container is paused.\n\n'
            else:
                raise e
            start_req_timer = False
        else:
            # msg in chat that all is well
            s += ' established\n\n'
        print(s, end='')

        # request timer
        global req_timer
        req_timer = RequestTimer()
        if start_req_timer:
            req_timer.start()
            # msg in chat
            s = '  Everything is ok:\n'
            s += '   Request timer started.\n\n'
        else:
            s = "  Request timer didn't start!\n\n"

        s += 'Use "help" for a list of commands'
        print(s)

    def default(self, line):
        '''Show message and help function if command is unknown.'''
        print('This command doesn\'t exist!')
        self.onecmd('help')

    def emptyline(self):
        '''Nothing happens.'''
        return None

    # ---- string utilities ----

    def print_iterable(self, i, indent=' '):
        '''Creates a string from an iterable object depending on the type'''
        s = ''
        if isinstance(i, list):
            for item in i:
                # if isinstance(item, dict):
                # 	for subitem in item.items():
                # 		s += f'{indent}{subitem[0]}: {subitem[1]}\n'
                # 	s += '\n'
                # else:
                s += f'{indent}{item}\n'
        elif isinstance(i, dict):
            for item in i.items():
                s += f'{indent}{item[0]}: {item[1]}\n'
        return s

    # ---- commands ----

    def do_request(self, arg):
        '''Save answer of API1 or API2 request as .json file in "requests"'''
        if arg == '':
            s = 'Usage: request api1|api2\n\n'\
                'Save response of api in folder "requests"'
            print(s)
        elif arg == 'api1':
            try:
                dt = datetime.now()
                times = dt.strftime('%Y.%m.%d_%H:%M:%S')
                name = f'api1_{times}.json'
                f = open('../requests/' + name, mode='x')
                json.dump(api1.request(), f, indent='\t')
            except FileExistsError:
                print('You cant send requests multiple times per second!')
            except ApiConnectionError:
                print('Connection to Api1 failed!')
            except ApiTimeoutError:
                print("Api didn't respond!")
            else:
                print(f'file {name} created')
        elif arg == 'api2':
            try:
                dt = datetime.now()
                times = dt.strftime('%Y.%m.%d_%H:%M:%S')
                name = f'api2_{times}.json'
                f = open('../requests/' + name, mode='x')
                json.dump(api2.request(), f, indent='\t')
            except FileExistsError as e:
                print('You cant send requests multiple times per second!')
            except ApiConnectionError:
                print('Connection to Api2 failed!')
            except ApiTimeoutError:
                print("Api didn't respond!")
            else:
                print(f'file {name} created')

    def do_reqTimer(self, arg):
        '''Start or stop the request timer'''
        global req_timer
        if arg == '':
            s = 'Usage: reqTimer OPTION\n\n'
            s += 'Options:\n'
            s += ' start : Starts the request timer\n'
            s += ' stop : Stop the request timer\n\n'
            s += 'Current state: '
            if req_timer.run:
                s += 'running\n'
            else:
                s += 'stopped!\n'
            print(s)
        elif arg == 'start':
            if req_timer.run == False:
                req_timer.start()
                print('timer started!')
            else:
                print('timer has already been started!')
        elif arg == 'stop':
            req_timer.run = False
            print('timer stopped!')

    def do_loadDownloadFiles(self, arg): # under construction
        path = '../add_data_to_db/'
        file_list = os.listdir(path)
        dfiles = []
        for i, e in enumerate(file_list):
            if os.path.isfile(path + e) and e.startswith('') and e.endswith('.csv'):
                dfiles.append(e)
        for e in dfiles:
            print(e)

    def do_mendDB(self, arg):
        if arg == 'load':
            print("\ntemp load\n")
            pass
        elif arg == 'gaps':
            db.get_entries()
            db.get_gaps()
        else:
            s = '\nUnknown command \''+arg+'\' Usage: mendDB COMMAND\n\n'
            s += 'Commands:\n'
            s += ' load : temp load.\n'
            s += ' gaps : temp gaps.\n'
            print(s)

    def do_config(self, arg):
        '''View and change configuration'''
        # messages
        def usage_and_sections_msg(list_str): return 'Usage: config SECTION [KEY VALUE|add VALUE|rm VALUE]\n\n'\
            'Show and change configuration values\n\n'\
            'sections:\n' + list_str
        def list_usage_msg(
            section): return f'Usage: config {section} [add VALUE|rm VALUE]\n'
        def dict_usage_msg(
            section): return f'Usage: config {section} [KEY VALUE]\n'
        def type_not_supported_msg(section): return f'{section} is a {type(section)}!\n'\
            'This type is not supported, please change the config file'
        def section_not_existing_msg(section): return f'Section "{section}" doesn\'t exist!\n'\
            'Use "config" to view sections\n'

        args = arg.rstrip('\n').split()

        if len(args) == 0:  # config
            msg = usage_and_sections_msg(
                self.print_iterable(list(config.data)))

        elif len(args) == 1:  # config SECTION
            if args[0] not in config.data.keys():  # Section does not exists
                msg = section_not_existing_msg(args[0])
            elif isinstance(config.data[args[0]], list):  # Section is a list
                msg = list_usage_msg(args[0])
                msg += '\nCurrent values:\n'
                msg += self.print_iterable(config.data[args[0]])
            elif isinstance(config.data[args[0]], dict):  # Section is a dictionary
                msg = dict_usage_msg(args[0])
                msg += '\nCurrent settings:\n'
                msg += self.print_iterable(config.data[args[0]])
            else:
                msg = type_not_supported_msg(config.data[args[0]])

        elif len(args) == 3:  # config SECTION KEY VALUE | config SECTION add/rm VALUE
            if args[0] in config.data.keys():  # Section exists
                if isinstance(config.data[args[0]], list):  # Section is a list
                    if args[1] == 'add':
                        # check syntax
                        if args[0] == 'requestTimes' and not self.check_time_syntax(args[2]):
                            msg = 'Wrong time format!\n\n'\
                                'syntax must be "hh:mm"\n"x" represents any digit\n'
                            # More information in help for requestTimer ??
                        # prevent duplicates
                        elif args[2] in config.data[args[0]]:
                            msg = 'Value is already in list!\n'
                            msg += self.print_iterable(config.data[args[0]])
                        else:
                            config.data[args[0]].append(args[2])
                            config.data[args[0]].sort()
                            msg = self.print_iterable(config.data[args[0]])
                    elif args[1] == 'rm':
                        try:
                            config.data[args[0]].remove(args[2])
                        except ValueError:
                            pass
                        msg = self.print_iterable(config.data[args[0]])
                    else:
                        msg = 'Unknown argument!\n'
                        msg += list_usage_msg(args[0])
                # Section is a dictionary
                elif isinstance(config.data[args[0]], dict):
                    if args[1] in config.data[args[0]].keys():
                        if args[1] == 'port':
                            config.data[args[0]][args[1]] = int(args[2])
                        elif args[1] == 'show_message':
                            if args[2] in ['True', 'true', '1']:
                                config.data[args[0]][args[1]] = True
                            elif args[2] in ['False', 'false', '0']:
                                config.data[args[0]][args[1]] = False
                            else:
                                pass
                        else:
                            config.data[args[0]][args[1]] = args[2]
                        msg = self.print_iterable(config.data[args[0]])
                    else:
                        msg = f'Key "{args[1]}" does not exist!\n'
                        msg += 'Use "config SECTION" for more info\n'
                else:
                    msg = type_not_supported_msg(config.data[args[0]])
            else:
                msg = section_not_existing_msg(args[0])

        else:
            msg = f'{len(args)} arguments given. Expected 1 or 3\n'
        print(msg)

    def do_debug(self, arg):
        '''Provides different debug functionalities'''
        if arg == 'add':
            time = time_utils.get_now(string=True)
            req_timer.make_req(time, debug=True)
        elif arg == 'dAdd':
            req_timer.trigger_debug_action = True
            print('trigger: ' + str(req_timer.trigger_debug_action))
        elif arg == 'rm':
            try:
                db.rm_last()
            except DBWritingError:
                print('--> line could not be removed!')
            except DBTimeoutError:
                print("Database didn't respond!")
            else:
                print('--> line removed')
        elif arg == 'pingDB':
            try:
                db.ping()
            except DBConnectionError:
                print("Connection to the database failed!")
            except DBTimeoutError:
                print("Database didn't respond!")
            else:
                print('Connection to the database established')
        elif arg == 'pingApi':
            '''Checks if API1 is working correctly and if data is complete'''
            em = "There is a problem with the Api:"
            try:
                Api1().get_values()
            except ApiConnectionError:
                em += "\n ApiConnectionError"
                em += "\n The API1 didn't respond!"
            except DataIncompleteError:
                em += "\n DataIncompleteError"
                em += "\n The data of the api request is incomplete!"
            except WStOfflineError:
                em += "\n WStOfflineError"
                em += "\n The data of the request is outdated!"
            except ApiTimeoutError:
                em += "\n ApiTimeoutError"
                em += "\n Occurs when the api doesn't respond"
            else:
                em = "Everything is ok"
            em += "\n"
            print(em)
        else:
            s = '\nUnknown command \'' + arg + '\' Usage: debug COMMAND\n\n'
            s += 'Commands:\n'
            s += ' add : Adds row to db with current weather data.\n'
            s += ' dAdd : like \'add\' but called by the thread of req_timer.\n'
            s += ' rm : Remove last row of db.\n'
            s += ' pingDB : Check and (re-)establish the connection with the database.\n'
            s += ' pingApi : Check the connection with the Api.\n'
            print(s)

    def do_restart(self, arg):
        '''Restart program and keep the cmd history.'''
        restart()

    def do_quit(self, arg):
        '''Exit program.'''
        quit()

def restart():
    '''Save the cmd history and restart in a new thread'''
    req_timer.run = False
    readline.write_history_file('.cmd_history')
    config.save()
    path = f'"{os.path.abspath(__file__)}"'
    os.execl(sys.executable, path, sys.argv[0], 'restart')

def quit():
    '''Exit the program'''
    req_timer.run = False
    config.save()
    sys.exit()

if __name__ == '__main__':
    if 'restart' in sys.argv:
        readline.read_history_file('.cmd_history')

    time_utils = TimeUtils()
    config = Configuration()

    db = None
    api1 = None
    api2 = None
    req_timer = None

    cli = CLI()
    # enables autocompletion depending on the system debian or Windows
    if os.name == 'posix':
        readline.parse_and_bind('bind ^I rl_complete')
    else:
        readline.parse_and_bind('tab: complete')
    cli.cmdloop()

    # dl = Download()
    # dl.load('_1-3-22_00-00_1_Day_1647772733_v2.csv')
