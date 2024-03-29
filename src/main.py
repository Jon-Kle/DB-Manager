from customExceptions import * # custom exceptions and TimeoutHelper
import download_file # module for extracting the range of a download file
import sys, os, time # System
from datetime import datetime, timedelta # for names of request files and RequestTimer
import email.utils # for conversion of rfc822 to datetime
from threading import Thread # For RequestTimer
import hmac # Hash function for WeatherLink-API
import pymysql, requests, json # APIs and database
import cmd # Command line (readline gets only imported if the config variable for it is true)
import csv # Read download-files
import emailMessages # remote error messages
import logging # used in Configuration.init_logging()
from logging import getLogger # get log instance with certain name
from logging.handlers import RotatingFileHandler # Create log files with a certain size

class TimeUtils:
    '''
    Class to help with datetime objects and handle the timing of request

    Methods
    -------
    get_now(string=False):
            returns datetime object of CET timezone
    get_next_req_time(now=None):
            Calculates next_req.
    '''

    def get_now(self, string=False):
        '''
        Return a naive datetime object of the CET zone

                parameters:
                        string (bool): lets this method return a string of
                            the datetime object in iso format.
        '''
        now = datetime.utcnow() + timedelta(hours=1)  # uses CET, ignores DST
        now = now.replace(microsecond=0)
        if string:
            return now.isoformat(sep=' ')
        return now

    def get_next(self, now=None) -> datetime:
        '''
        Calculate time of next request.

        is always at xx:00 or at xx:30

                parameters:
                        now (datetime): starting point for calculation.
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
    A class to read and write the config files and to initiate logging.

    Attributes
    ----------
    data: dict
            content of the config.json file
    excluded: list
            all the config values that are sensible and don't belong in the config file
    secrets: dict
            content of the dat.json file (sensible information)

    Methods
    -------
    __init__():
            Reads the config.json and dat.json files and merges their data
    init_logging():
            Configures and initiates logging
    save():
            Separates the loaded data and writes it into the config.json and the dat.json files.
    '''

    def __init__(self):
        '''
        Open the config.json file and the dat.json file
        and save its content in the attribute "data",
        also keep track of which values were in the dat.json file.
        '''
        self.data = None
        self.excluded = []
        # load config file
        f = open('res/config.json')
        s = f.read()
        self.data = json.loads(s)
        f.close()
        # load dat file
        f = open('res/dat.json')
        s = f.read()
        self.secrets = json.loads(s)

        # check for empty values
        for i, k1 in enumerate(self.data.keys()):
            if i > 0:
                for k2 in self.data[k1].keys():
                    if self.data[k1][k2] == '':
                        # replace them with the data of self.secrets
                        self.data[k1][k2] = self.secrets[k1][k2]
                        # not which values were not in config.json
                        self.excluded.append((k1, k2))

    def init_logging(self):
        '''
        Create a file handler and a formatter and attach them both to the root logger.
        Like this every new instance of logger uses this handler and formatter.
        '''
        log_handler = RotatingFileHandler(
            filename='DB-Manager.log',
            maxBytes=10*1024*1024, #10MiB
            backupCount=5
        )
        log_formatter = logging.Formatter(
            fmt='%(asctime)s %(levelname)s %(name)s: %(msg)s',
            datefmt='%d.%m.%Y %H:%M:%S'
        )
        log_handler.setFormatter(log_formatter)
        level = logging.INFO
        if debugging:
            level = logging.DEBUG
        logging.basicConfig(
            level=level, # set, which messages get displayed in the log files
            handlers=[log_handler]
        )

    def save(self):
        '''
        Separate the values of config.json and dat.json using self.excluded
        and write them into their respective files
        '''
        # remove excluded values from self.data and move it into self.secrets
        for e in self.excluded:
            k, k2 = e[0], e[1]
            self.secrets[k][k2] = self.data[k][k2]
            self.data[k][k2] = ''

        # save config file
        configFile = open('res/config.json', 'w')
        json.dump(self.data, configFile, indent='\t')
        configFile.close()
        # save dat file
        datFile = open('res/dat.json', 'w')
        json.dump(self.secrets, datFile, indent='\t')
        configFile.close()

class Database:
    '''
    A class to represent the MySQL Database.

    Attributes
    ----------
    config: dict
            configuration data for the database connection
    con: pymysql.connection
            connection object of pymysql
            This is None, if the connection is not established.
    cursor: pymysql.cursors.DictCursor
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
            removes the last entry in the database
    check_writing_to_db():
            Writes and deletes one line to the database
            to check if writing to the db is possible.
    get_entries():
            Reads all entry dates of the database data and returns a list
            of tuples with the data if any possible entry exists in the db.
    get_gaps(entries):
            Reads the list of "entries" returned from get_entries() and finds all
            the gaps in the list.
    load_file(file_name):
            Reads the .csv file "file_name" and adds its  data to the db.
    '''

    def __init__(self):
        self.config = config.data['db']

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

        try:
            self.con = pymysql.connect(
                port=self.config['port'],
                host=self.config['host'],
                user=self.config['user'],
                password=self.config['password'],
                database=self.config['database'],
                cursorclass=pymysql.cursors.DictCursor,
                read_timeout=int(self.config['timeoutMs']/1000))
        except pymysql.err.OperationalError as e:
            raise DBConnectionError(e)
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
        Add a row to the end of db with the values from "values".

                Parameters:
                        values (list): Values that get written into the db

                Exceptions:
                        DBWritingError
                        DBTimeoutError
        '''
        query_string = "INSERT INTO `{table}` (`entryDate`, `temp`, `pressure`, `hum`, `windspeed`, `winddir`, `rainrate`, `uvindex`)\
 VALUES ( %s, %s, %s, %s, %s, %s, %s, %s);".format(table=self.config['table'])
        # this function gets executed in another thread
        def exec_():
            try:
                self.cursor.execute(query_string, values)
                self.con.commit()
                return True, None
            except pymysql.Error as e:
                return None, DBWritingError(e)
            except AttributeError as e:
                return None, DBConnectionError(e)
        timeout = TimeoutHelper(exec_)
        # this starts a separate thread with exec_() and a timer
        # finishes the timer before the function has finished, a timeout error is raised
        timeout.timer(self.config['timeoutMs'], DBTimeoutError)

    def rm_last(self):
        '''
        Remove last row in the table.

                Exceptions:
                        DBWritingError
                        DBTimeoutError
        '''
        def exec_():
            table=self.config['table']
            try:
                self.cursor.execute(
                    f"DELETE FROM `{table}` WHERE -1 ORDER BY entryDate DESC LIMIT 1;")
                self.con.commit()
                return True, None
            except pymysql.Error as e:
                return None, DBWritingError(e)
        timeout = TimeoutHelper(exec_)
        # this starts a separate thread with exec_() and a timer
        # finishes the timer before the function has finished, a timeout error is raised
        timeout.timer(self.config['timeoutMs'], DBTimeoutError)

    def check_writing_to_db(self):
        '''
        Check if writing to the db is possible by adding and removing one line to the db.

            Exceptions:
                    DBWritingError
                    DBTimeoutError
        '''
        def exec_():
            table = self.config['table']
            try:
                # example line that gets removed instantly
                self.cursor.execute(f"INSERT INTO `{table}` (`entryDate`, `temp`, `pressure`, `hum`, `windspeed`, `winddir`, `rainrate`, `uvindex`)\
 VALUES ('0000-01-01 00:00:00', '26.9', '1014.7', '39', '1.60934', 'SO', '0.0', '2.2');")
                self.cursor.execute(f"DELETE FROM `{table}` WHERE entryDate = '0000-01-01 00:00:00';")
                self.con.commit()
                return True, None
            except pymysql.Error as e:
                return None, DBWritingError(e)
        timeout = TimeoutHelper(exec_)
        # this starts a separate thread with exec_() and a timer
        # finishes the timer before the function has finished, a timeout error is raised
        timeout.timer(self.config['timeoutMs'], DBTimeoutError)

    def get_entries(self):
        '''
        Return a list of tuples with all the possible entries and the information if an entry exists in the db
        format: [(entryDate, bool), (entryDate, bool), ...]

                Returns:
                        [(entryDate: datetime, exists: bool), ...]

                Exceptions:
                        DBConnectionError
                        DBTimeoutError
                        DBNoDataReceivedError
        '''
        def get_data():
            table = self.config['table']
            try:
                db.cursor.execute(f'SELECT entryDate FROM {table} ORDER BY entryDate ASC')
                data = db.cursor.fetchall()
                return data, None
            except AttributeError as e:
                return None, DBConnectionError(e)
        timeout = TimeoutHelper(get_data)
        data = timeout.timer(self.config['timeoutMs'], DBTimeoutError)
        data = [e['entryDate'] for e in data] # only get a list of the entryDates
        if data == []:
            raise DBNoDataReceivedError()

        entries = []
        first_str = self.config["mendStartTime"] # looks like "2012,7,9,0,0,0"
        first_l = first_str.split(sep=",") # separates str into year, month, day, hour, minute, second
        first = datetime(*[int(s) for s in first_l]) # gives all values in first_l as separate arguments
        last = time_utils.get_next()

        current = first
        index = 0
        while current != last:
            if current == data[index]:
                entries.append((current, True))
                if index != len(data)-1: # if not the last index
                    index += 1
            else:
                entries.append((current, False))
            current += timedelta(minutes=30)
        return entries

    def get_gaps(self, entries):
        '''
        Read a list of entries and find all gaps in this list.
        Gaps that are saved in add_data/.remaining_gaps are ignored because they can not be fixed (missing data).

                Parameters:
                        entries (list): list of tuples returned by get_entries()

                Returns:
                        [(start: datetime, end: datetime, count: int), ...]
        '''
        try:
            f = open('add_data/.remaining_gaps')
            gap_str_l = f.readlines()
            # parse into datetime objects
            gap_l = []
            for l in gap_str_l:
                if l == '':
                    raise FileNotFoundError
                l.strip('\n') # looks like "2012-01-01T00:00:00 2013-01-01T00:00:00"
                l2 = l.split()
                gap_l.append((datetime.fromisoformat(l2[0]), datetime.fromisoformat(l2[1])))
            f.close()
        except FileNotFoundError:
            gap_l = []
        if len(gap_l) > 0:
            saved_gap_index = 0
        else: 
            saved_gap_index = None

        previous_status = True
        gaps = []
        entries.append((entries[-1][0]+timedelta(minutes=30), True))
        for i, e in enumerate(entries):
            # e[0] is entryDate:datetime
            # e[1] is exists:bool
            current_status = e[1]

            if len(gap_l) > 0 and not e[1]: # if there are saved gaps and the current entry is missing
                # jump all the saved gaps that don't affect the missing entry
                while e[0] > gap_l[saved_gap_index][1]: # if the missing entry is after the end of the first saved gap
                    saved_gap_index += 1
                    if saved_gap_index == len(gap_l):
                        saved_gap_index -= 1 # jump back to previous to avoid indexOutOfBounds error
                        break
                # if the missing entry is inside of current saved gap
                if e[0] >= gap_l[saved_gap_index][0] and e[0] <= gap_l[saved_gap_index][1]:
                    current_status = True # ignore that the entry is missing

            if not current_status and previous_status:
                # start of a new gap
                start = e[0]
                count = 1
            elif not current_status and not previous_status:
                # middle of a gap
                count += 1
            elif current_status and not previous_status:
                # end of a gap
                end = entries[i-1][0]
                gaps.append((start, end, count))
            previous_status = current_status
        return gaps

    def load_file(self, file_name):
        '''
        Read the .csv file with the name file_name and add its contents to the database.
        
                Parameters:
                    file_name (str): Name of file to be read

                Returns:
                    new_data_length: int
                
                Exceptions:
                    DBConnectionError
                    DBTimeoutError
        '''
        # read file with name and save data as list
        csv_file = open(file_name, encoding='mac_roman') # encoding specific for the .csv files of Davis instruments
        reader = csv.reader(csv_file)
        data = []
        for row in reader:
            if reader.line_num > 6: # everything before line 7 is only for humans
                # sort out the lines when nothing is entered ('--')
                if '--' in [row[0], row[7], row[1], row[10], row[13], row[14], row[23], row[28]]:
                    continue
                else:
                    # transform datetime
                    date_time = row[0].split(' ')
                    e_date = date_time[0].split('/')
                    e_time = date_time[1].split(':')
                    entry_date = datetime(
                    int('20' + e_date[2]), # year
                    int(e_date[1]), # month
                    int(e_date[0]), # day
                    int(e_time[0]), # hour
                    int(e_time[1])) # minute
                    # correct entry_dates to be always at the half hour
                    if entry_date.minute%30 != 0:
                        difference = entry_date.minute%30
                        if difference >= 15:
                            entry_date += timedelta(minutes=30-difference)
                        else:
                            entry_date -= timedelta(minutes=difference)
                    # replace commas with dots so Python can understand it
                    pressure = row[1].replace( ',', '.')
                    rainrate = row[23].replace( ',', '.')
                    data.append([entry_date, row[7], pressure, row[10], row[13], row[14], rainrate, row[28]])

        # sort out entries that are not in a gap
        gaps = self.get_gaps(self.get_entries())
        gap_index = 0
        data_index = 0
        new_data = []
        while True:
            if data[data_index][0] < gaps[gap_index][0]: # if data earlier than next gap
                data_index += 1
            elif data[data_index][0] > gaps[gap_index][1]: # if data later than next gap
                gap_index += 1
            else: # if data in gap
                # add row to new_data
                data[data_index][0] = data[data_index][0].isoformat(sep=' ') # transform datetime into string
                new_data.append(data[data_index])
                data_index += 1
            if data_index == len(data) or gap_index == len(gaps):
                break

        def write_data():
            try:
                db.cursor.executemany("INSERT INTO `{table}` (`entryDate`, `temp`, `pressure`, `hum`, `windspeed`, `winddir`, `rainrate`, `uvindex`)\
 VALUES ( %s, %s, %s, %s, %s, %s, %s, %s);".format(table=self.config['table']), new_data)
                db.con.commit()
                return True, None
            except AttributeError as e:
                return None, DBConnectionError(e)
        timeout = TimeoutHelper(write_data)
        timeout.timer(self.config['timeoutMs'], DBTimeoutError)

        return len(new_data)

class Api1:
    '''
    A class to represent the WeatherLink API V1

    This API is very simple. It takes over all credentials directly without any
    security measures, except for the HTTPS protocol.

    API documentation: https://www.weatherlink.com/static/docs/APIdocumentation.pdf

    Attributes
    ----------
    config: dict
            configuration data from which url, user, password and token are extracted
    url: str
            the URL that is used for the request
    user: str
            device-ID (DID) of the Data Logger mounted to the console of the station
    password: str
            the password that is also used to log into the WeatherLink website
    token: str
            unique API-Token. Don't share with anyone!
            If compromised generate a new one at https://www.weatherlink.com/account

    Methods
    -------
    check():
            Check if connection works and if the data is complete and up to date.
    request():
            Makes an HTTPS request with the given values.
            Returns the answer in json format as a dict.
    get_values(time_=None):
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
        Check if the connection works, if the data is complete and up to date.

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

                Returns:
                        response: dict

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

    def get_values(self, time_=None):
        '''
        Make API1 Request and get selected values to form a list.

                Parameters:
                        time (str): overwrites the entryDate value in val_list

                Returns:
                        list of values from the weather station

                Exceptions:
                        ApiConnectionError
                        DataIncompleteError
                        WStOfflineError
                        ApiTimeoutError
        '''
        if not time_:
            time_ = time_utils.get_now(string=True)
        # request Api1
        data = self.request()

        # check if data is up to date
        datestr = data['observation_time_rfc822']
        datet = email.utils.parsedate_to_datetime(datestr)
        # subtract an hour from the time_ value returned by the API when DST is active (summer time)
        datet = datet.replace(tzinfo=None)-timedelta(hours=time.localtime().tm_isdst)
        now = time_utils.get_now()
        deltat = now - datet
        if deltat > timedelta(minutes= self.config['dataMaxAge']):
            raise WStOfflineError(datet)

        val_list = {}
        val_list['time'] = time_
        error = None
        def error_handler():
            '''Store appearing errors, don't raise them yet'''
            if error == None:
                self.error = DataIncompleteError()
            error.missing.append(e.args[0])

        # gather and format data values if existing
        try:
            # temperature
            val_list['temp'] = data['temp_c']
        except KeyError as e:
            error_handler()
        try:
            # pressure
            val_list['pressure'] = data['pressure_mb']
        except KeyError as e:
            error_handler()
        try:
            # humidity
            val_list['hum'] = data['relative_humidity']
        except KeyError as e:
            error_handler()
        try:
            # wind speed
            in_kmh = float(data['wind_mph'])
            in_kmh *= 1.60934 # convert from mph into km/h
            val_list['wind_speed'] = str(in_kmh)
        except KeyError as e:
            error_handler()
        try:
            # wind direction
            w_dir = int(data['wind_degrees'])
            w_dir_str = None
            # convert degrees into compass directions
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
            val_list['wind_dir'] = w_dir_str
        except KeyError as e:
            error_handler()
        try:
            # rain rate per hour
            rain_rate_in_mm = float(data['davis_current_observation']['rain_rate_in_per_hr']) * 25.4 # convert from in to mm
            val_list['rain_rate_per_hr'] = str(rain_rate_in_mm)
        except KeyError as e:
            error_handler()
        try:
            # uv index
            val_list['uv_index'] = data['davis_current_observation']['uv_index']
        except KeyError as e:
            error_handler()

        if error: raise error # now raise an error if one occurred

        return list(val_list.values())

class Api2:
    '''
    A class to represent the API V2 (Not actively used)

    This API is more complex than the API V1.
    It is more sophisticated and uses an HMAC algorithm with sha256 for more security

    API documentation: https://weatherlink.github.io/v2-api/

    Attributes
    ----------
    config: dict
            configuration data from which url, key, secret and station_id are extracted
    url: str
            the URL that is used for the request
    key: str
            used to identify the user making the request
    secret: str
            used to calculate the signature for the request. Don't share with anyone!
            If compromised generate a new one at https://www.weatherlink.com/account
    station_id: str
            ID which identifies the weather station the data is requested from

    Methods
    -------
    check():
            Checks the connection with the Api
    request():
            Makes an HTTPS request with the values and the calculated signature.
    get_stations():
            Makes an HTTPS request to get all the possible station IDs and returns the answer in a compact format.
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
        Return dict from Api2 https request.

                Exceptions:
                        ApiConnectionError
                        ApiTimeoutError
        '''
        # create api signature for verification of the user
        t = int(time.time())
        param_str = f'api-key{self.key}station-id{self.station_id}t{t}'
        hmac_obj = hmac.new(str.encode(self.secret), str.encode(param_str), 'sha256')
        api_signature = hmac_obj.hexdigest()

        payload = {
            'api-key': self.key,
            't': t,
            'api-signature': api_signature
        }
        # this function gets executed in another thread
        def req():
            try:
                r = requests.get(self.url + 'current/' + self.station_id + '?', params=payload)
                return r, None
            except requests.ConnectionError as e:
                return None, ApiConnectionError(e)
        timeout = TimeoutHelper(req)
        # this starts the thread with req() and a timer
        # if the timer finishes before the function is executed, a timeout error is raised
        r = timeout.timer(self.config['timeoutMs'], ApiTimeoutError)

        return r.json()  # parses json response to dict

    def get_stations(self):
        '''
        Return IDs and names from weatherlink Stations as dict.
        This is for configuration purposes only.

                Exceptions:
                        ApiConnectionError
                        ApiTimeoutError
        '''
        # create api signature for verification of the user
        t = int(time.time())
        param_str = f'api-key{self.key}t{t}'
        hmac_obj = hmac.new(str.encode(self.secret), str.encode(param_str), 'sha256')
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

        stations = r.json()
        stations_compact = []
        for e in stations['stations']:
            new_station = {'station_id': e['station_id'], 'station_name': e['station_name']}
            stations_compact.append(new_station)
        return stations_compact  # return stations as dict

class RequestTimer:
    '''
    A class that periodically loads data into the database

    Attributes
    ----------
    config: dict
            configuration data for requestTimer
    show_msg: bool
            variable to set message visibility in the console as a configuration
    msg: bool
            variable to toggle message visibility during runtime
    run: bool
            indicates when the timer is running
    trigger_debug_request: bool
            variable to create requests in the timer thread for debugging
    next_req: datetime
            time when the next line will be added to the database
    seconds_till_next: int
            seconds till the next requests gets triggered
    thread: Thread
            thread for the timer

    Methods
    -------
    start():
            Creates thread for the timer and starts it.
    timer():
            Counts seconds_till_next and calls make_req().
    make_req(time=None, msg=True, debug=False):
            Makes request and adds row to the database.
    line_msg(time, values, debug=False):
            Builds message for when a line is added to the database
    '''

    def __init__(self):
        # configuration
        self.config = config.data['requestTimer']
        self.show_msg = self.config['show_message']
        self.msg = True
        self.run = False
        self.trigger_debug_request = False

    def start(self):
        '''Initiate thread with timer().'''
        log = getLogger('REQUEST TIMER')
        self.next_req = time_utils.get_next()
        log.info('next request: ' + (self.next_req + timedelta(hours=time.localtime().tm_isdst)).isoformat(sep=' '))
        self.seconds_till_next = (self.next_req-time_utils.get_now()).seconds

        self.thread = Thread(name='timer', target=self.timer, daemon=True)
        self.thread.start()

    def timer(self):
        '''Time requests.'''
        log = getLogger('REQUEST TIMER')
        i = self.seconds_till_next + 1
        self.run = True
        try:
            while self.run:
                if self.trigger_debug_request:
                    self.trigger_debug_request = False
                    log.info('starting debug request')
                    self.make_req(time=time_utils.get_now(string=True), debug=True)

                if i > 0:
                    time.sleep(1)
                    i -= 1
                else:
                    log.info('starting request')
                    self.make_req(msg=self.msg)
                    # calculate next request
                    self.next_req = time_utils.get_next()
                    log.info('next request: ' + (self.next_req + timedelta(hours=time.localtime().tm_isdst)).isoformat(sep=' '))
                    self.seconds_till_next = (self.next_req-time_utils.get_now()).seconds
                    i = self.seconds_till_next + 1
        except BaseException as e:
            log.error('unhandled exception occurred')
            emailMessages.send_error(e)
            raise e

    def make_req(self, time=None, msg=True, debug=False):
        '''
        Get values from Api1.get_values() and add them to the database.
        Trigger message if self.show_msg and self.msg is true.

                Parameters:
                        time (str): overwrites the time value for the new line
                        msg (bool): determines if a message for the added line gets shown
                        debug (bool): gets passed on to line_msg()
        '''
        log = getLogger('REQUEST TIMER')

        if time == None:
            time = self.next_req.isoformat(sep=' ')

        try:
            db.ping() # reconnect to database if not connected
        except (DBConnectionError, DBTimeoutError):
            pass
        
        db_errors_resolved = False
        api_errors_resolved = False
        try:
            # get Values
            values = api1.get_values(time)
        except BaseException as e:
            log.error('API1 request failed: ' + e.__class__.__name__)
            if isinstance(e, ApiConnectionError):
                s = f'\n--> {time} - Connection with Api1 failed!\n'
                emailMessages.send_warning(e)
            elif isinstance(e, DataIncompleteError):
                log.error('missing data: ' + str(e.missing))
                s = f'\n--> {time} - Data of request is incomplete!\n'
                s += ' missing Data:\n'
                s += cli.print_iterable(e.missing, indent=' - ') + '\n'
                emailMessages.send_warning(e)
            elif isinstance(e, WStOfflineError):
                log.error('last online: ' + e.last_online.isoformat(sep=" "))
                s = f'\n--> {time} - Data of request is outdated!\n'
                s += ' last online: '
                s += e.last_online.isoformat(sep=" ") + '\n'
                emailMessages.send_warning(e)
            elif isinstance(e, ApiTimeoutError):
                s = f'\n--> {time} - The request timed out!\n'
                emailMessages.send_warning(e)
            else: raise e
            log.error('request failed')
            s += cli.prompt
            print(s, end='')
        else:
            log.info('API1 request OK')
            api_errors_resolved = True
            try:
                # add row to db
                db.add_row(values)
            except BaseException as e:
                log.error('Database connection failed: ' + e.__class__.__name__)
                if isinstance(e, DBConnectionError):
                    s = f'\n--> {time} - Connection with db failed!\n'
                    emailMessages.send_warning(e)
                elif isinstance(e, DBWritingError):
                    s = f'\n--> {time} - Writing to db failed!\n'
                    emailMessages.send_warning(e)
                elif isinstance(e, DBTimeoutError):
                    s = f"\n--> {time} - The db didn't respond!\n"
                    emailMessages.send_warning(e)
                else: raise e
                log.error('request failed')
                s += cli.prompt
                print(s, end='')
            else:
                log.info('Database connection OK')
                db_errors_resolved = True
                # message
                if self.show_msg and msg:
                    self.line_msg(time, values, debug=debug)
                log.info('request successful')
        if db_errors_resolved or api_errors_resolved:
            resolved_list = []
            if api_errors_resolved:
                resolved_list.extend(['ApiConnectionError', 'DataIncompleteError', 'WStOfflineError', 'ApiTimeoutError'])
            if db_errors_resolved:
                resolved_list.extend(['DBConnectionError', 'DBWritingError', 'DBTimeoutError'])
            emailMessages.resolved(resolved_list)

    def line_msg(self, time, values, debug=False):
        '''Build message for when a new line is added to the database.

                Parameters:
                        time (str): string that shows when the request was made
                        values (list): list with values from the request
                        debug (bool): changes the look of the message
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
    prompt: str
            shown in front of every new prompt

    Methods
    -------
    preeloop():
            Runs before cmdloop() starts. Tests and shows if all parts of the program work.
    default():
            Gets executed if command is unknown.
    emptyline():
            Gets executed if empty command ('') is entered.
     --- string utilities ---
    print_iterable():
            Returns string of iterable object i depending on the type.
     --- commands ---
    do_api1():
            actions regarding the Api1 (e.g. ping)
    do_api2():
            actions regarding the Api2 (nothing implemented yet)
    do_database():
            actions regarding the database (like "ping", "mend" and "gaps")
    do_reqTimer():
            controls the request timer (like "silence", "show", "start", "stop")
    do_config():
            View and change configuration.
    do_debug():
            Provides different debug functionalities.
    do_restart():
            Restart program and keep the command history.
    do_quit():
            Exit the program.
    '''
    prompt = '---(DB-Manager)> '

    def preloop(self):
        '''Check if the different parts of the program are working and build intro message.'''

        log = getLogger('STARTUP')

        s = '    -- DB-Manager --'
        print(s)

        start_req_timer = config.data['requestTimer']['timer_at_startup']

        # api1
        global api1
        api1 = Api1()
        s = '\n API1 request:'
        try:
            api1.check()
        except BaseException as e:
            log.error('API1 check failed: ' + e.__class__.__name__)
            # msg in chat
            s += ' failed!\n'
            if isinstance(e, ApiConnectionError):
                s += '  Connection could not be established!\n'
                s += '  Make sure, the connection to the internet is working.\n'
                s += '  It could also be that the API is offline.\n\n'
            elif isinstance(e, DataIncompleteError):
                log.error('missing data: ' + str(e.missing))
                s += '  Some data values are missing:\n'
                s += self.print_iterable(e.missing, indent='  - ')
                s += '  Make sure, the wires to the different sensors are properly connected!\n\n'
            elif isinstance(e, WStOfflineError):
                log.error('last online: ' + e.last_online.isoformat(sep=" "))
                s += '  The data is outdated!\n'
                s += f'   last online: {e.last_online.isoformat(sep=" ")}\n'
                s += '  Make sure, the weather-station is connected to the internet!\n\n'
            elif isinstance(e, ApiTimeoutError):
                s += '  The Api1 request timed out!\n'
                s += '  Make sure the connection to the internet is good.\n\n'
            else:
                raise e
            start_req_timer = False
        else:
            log.info('API1 OK')
            # msg in chat that all is well
            s += ' successful\n\n'
        print(s, end='')

        # api2 (not used)
        global api2
        s = ' API2 request:'
        try:
            api2 = Api2()
        except BaseException as e:
            log.error('API2 check failed: ' + e.__class__.__name__)
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
            log.info('API2 OK')
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
            log.error('Database check failed: ' + e.__class__.__name__)
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
            log.info('Database OK')
            # msg in chat that all is well
            s += ' established\n\n'
        print(s, end='')

        # request timer
        global req_timer
        req_timer = RequestTimer()
        if start_req_timer:
            log.info('start RequestTimer')
            req_timer.start()
            # msg in chat
            s = '  Everything is ok:\n'
            s += '   Request timer started.\n\n'
        else:
            log.info('RequestTimer did not start')
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

    def do_api1(self, arg):
        '''Actions regarding the API1'''
        log = getLogger('API1')
        if arg == 'ping':
            '''Checks if API1 is working correctly and if data is complete'''
            log.info('pinging')
            em = "There is a problem with the Api:"
            try:
                Api1().get_values()
            except ApiConnectionError:
                log.error('connection failed: ApiConnectionError')
                em += "\n ApiConnectionError"
                em += "\n The API1 didn't respond!"
            except DataIncompleteError as e:
                log.error('connection failed: DataIncompleteError')
                log.error('missing data: ' + str(e.missing))
                em += "\n DataIncompleteError"
                em += '  Some data values are missing:\n'
                s += self.print_iterable(e.missing, indent='  - ')
            except WStOfflineError as e:
                log.error('connection failed: WStOfflineError')
                log.error('last online: ' + e.last_online.isoformat(sep=" "))
                em += "\n WStOfflineError"
                em += "\n The data is outdated!"
                em += f'  last online: {e.last_online.isoformat(sep=" ")}\n'
            except ApiTimeoutError:
                log.error('connection failed: ApiTimeoutError')
                em += "\n ApiTimeoutError"
                em += "\n Occurs when the api doesn't respond"
            else:
                log.info('connection OK')
                em = "Everything is ok"
            em += "\n"
            print(em)
        else:
            s = '\nUnknown command \'' + arg + '\' Usage: api1 COMMAND\n\n'
            s += 'Commands:\n'
            s += ' ping : Check if the API1 is online.\n'
            print(s)
    
    def do_api2(self, arg):
        '''Actions regarding the API2'''
        log = getLogger('API2')
        print('this command does nothing at the moment')

    def do_database(self, arg):
        '''Connect to the database, Inspect and repair the gaps in the database made by downtime'''
        log = getLogger('DATABASE')
        arg = arg.rstrip('\n').split()
        if len(arg) == 0:
            arg.append('')
        if arg[0] == 'ping':
            log.info('pinging Database')
            try:
                db.ping()
            except DBConnectionError:
                log.error('connection failed: DBConnectionError')
                print("Connection to the database failed!")
            except DBTimeoutError:
                log.error('connection failed: DBTimeoutError')
                print("Database didn't respond!")
            else:
                log.info('connection OK')
                print('Connection to the database established')
        elif arg[0] == 'mend':
            # find available files and show enumerated list of names
            path = 'add_data/'
            file_list = os.listdir(path)
            download_files = [f for f in file_list if os.path.isfile(path + f) and f.endswith('.csv')]
            print('\nSelect the file you want to use for mending:')
            for i, e in enumerate(download_files):
                print('', i, '->', e)
            print(' q -> exit')
            file_name = ''
            # select file
            while True:
                ans = input('>')
                if config.data['readline']:
                    readline.remove_history_item(
                        readline.get_current_history_length()-1
                    )
                if ans.isdecimal() and int(ans) in range(len(download_files)):
                    file_name = download_files[int(ans)]
                    log.info('file chosen for mending: ' + file_name)
            
                    try:
                        new_entries = db.load_file(path + file_name)
                        log.info(f'{new_entries} entries added')
                        print(f'{new_entries} new entries added!')
                    except DBConnectionError as e:
                        log.error('connection failed: DBConnectionError')
                        print("Connection to the database was not established!")
                    except DBTimeoutError as e:
                        log.error('connection failed: DBTimeoutError')
                        print("Writing to the Database took too long!")

                    def add_df_range_to_file():
                        ''''''
                        # extract start and end of data from download file
                        date_range = download_file.extract_range(file_name) # looks like (start: datetime, end: datetime)

                        # read data from file
                        # this is very similar to the code in Database.get_gaps()
                        try:
                            f = open('add_data/.remaining_gaps')
                            range_str_l = f.readlines()
                            # parse into datetime objects
                            gap_l = []
                            for l in range_str_l:
                                if l == '':
                                    raise FileNotFoundError
                                l.strip('\n') # looks like "2012-01-01T00:00:00 2013-01-01T00:00:00"
                                l2 = l.split()
                                gap_l.append((datetime.fromisoformat(l2[0]), datetime.fromisoformat(l2[1])))
                            f.close()
                        except FileNotFoundError:
                            gap_l = []

                        # merge new range into gap file
                        new_ranges = []
                        first_date_placed = False
                        second_placed = False
                        # 0 -> the start of the file range is before the gap
                        # 1 -> the start of the file range is in the gap
                        state = None
                        first_i = None # index of gap_l
                        i = 0
                        while i < len(gap_l): # find position of the start of the file range
                            if date_range[0] < gap_l[i][0]: # start of file range is before gap
                                state = 0
                                first_i = i
                                first_date_placed = True
                                break
                            elif date_range[0] < gap_l[i][1]: # start of file range is in gap
                                state = 1
                                first_i = i
                                first_date_placed = True
                                break
                            new_ranges.append(gap_l[i])
                            i += 1
                        if not first_date_placed: # start of file range is after all gaps
                            new_ranges = gap_l + [date_range]
                        elif state == None: # only possible if gap_l is empty
                            new_ranges = [date_range] + gap_l
                        else:
                            while i < len(gap_l): # find position of second date in range
                                if date_range[1] < gap_l[i][0]: # before
                                    if state == 0:
                                        new_ranges.append(date_range)
                                    elif state == 1:
                                        new_ranges.append((gap_l[first_i][0], date_range[1]))
                                    new_ranges += gap_l[i:]
                                    second_placed = True
                                    break
                                elif date_range[1] < gap_l[i][1]: # in
                                    if state == 0:
                                        new_ranges.append((date_range[0], gap_l[i][1]))
                                    elif state == 1:
                                        new_ranges.append((gap_l[first_i][0], gap_l[i][1]))
                                    new_ranges += gap_l[i+1:]
                                    second_placed = True
                                    break
                                i += 1
                            if not second_placed:
                                new_ranges.append((date_range[0], date_range[1]))

                        # parse data to string
                        range_str = ''
                        for e in new_ranges:
                            range_str += datetime.isoformat(e[0]) + ' ' + datetime.isoformat(e[1]) + '\n'

                        # save new data in file
                        f = open('add_data/.remaining_gaps', mode='w')
                        f.write(range_str)
                        f.close

                    add_df_range_to_file()
                elif ans == 'q':
                    break
        elif arg[0] == 'gaps':
            try:
                entries = db.get_entries()
            except DBNoDataReceivedError as e:
                print('The database is empty!')
                return
            if len(arg) == 1:
                gaps = db.get_gaps(entries)
                # print amount of Gaps
                print('\nAmount of Gaps found:', len(gaps))
                # print list of Gaps
                for e in gaps:
                    if e[0] == e[1]: # if gap is only 1 entry long
                        print(' - ' + e[0].isoformat(sep=' '))
                        continue
                    s = ' - ' + e[0].isoformat(sep=' ')
                    s += ' -> ' + e[1].isoformat(sep=' ')
                    s += ' len: ' + str(e[2])
                    print(s)
            elif arg[1] == '-d':
                # calculate date one month later
                def next_end(current):
                    next_month = current.month+1 
                    if next_month > 12:
                        next_month = 1
                    while current.month != next_month:
                        current += timedelta(minutes=30)
                    return current
                # read data from file
                # this is very similar to the code in Database.get_gaps()
                try:
                    f = open('add_data/.remaining_gaps')
                    range_str_l = f.readlines()
                    # parse into datetime objects
                    range_l = []
                    for l in range_str_l:
                        l.strip('\n') # looks like "2012-01-01T00:00:00 2013-01-01T00:00:00"
                        l2 = l.split()
                        range_l.append((datetime.fromisoformat(l2[0]), datetime.fromisoformat(l2[1])))
                    f.close()
                except FileNotFoundError:
                    range_l = []
                if len(range_l) > 0:
                    range_index = 0
                else:
                    range_index = None
                # values for start and end points
                start_index = 0
                char = (' ', '\033[31m+\033[0m', '\033[32m@\033[0m') # characters used for printing with escape sequences for coloring
                start_of_table = entries[start_index][0].replace(day=1, hour=0, minute=0) # first day in month of start
                start_of_entries = entries[start_index][0] # date of first entry
                end_of_entries = entries[-1][0] # date of last entry
                end_of_table = next_end(end_of_entries).replace(day=1, hour=0, minute=0) # first day in month after end
                # preparations
                current = start_of_table
                end = next_end(start_of_table)
                empty = True # table starts with data that is not available
                index = start_index # index to track entries
                print_table = True
                while True:
                    table = ''
                    start = current # for information above table
                    while current != end:
                        if current == start_of_entries: # printing of available values and index counting starts
                            empty = False
                        if current == end_of_entries: # ends
                            empty = True

                        if empty == True: # printing if no data available
                            table += char[0]
                        elif empty == False: # printing if data available
                            if entries[index][1]: # If entry exists
                                table += char[2]
                            else: # if entry does not yet exist
                                # check if entry could exist (check for saved gaps in the file)
                                if range_index != None:
                                    while current > range_l[range_index][1]:
                                        range_index += 1
                                        if range_index == len(range_l):
                                            range_index -= 1
                                            break
                                    if current >= range_l[range_index][0] and current <= range_l[range_index][1]:
                                        table += char[0]
                                    else:
                                        table += char[1]
                                else: table += char[1]

                        if current.hour == 23 and current.minute == 30: # at line end
                            table += ']\n['
                        if empty == False:
                            index += 1
                        current += timedelta(minutes=30)
                    if print_table:
                        # assembling, cleaning and printing table
                        table = table.rstrip('\n[')
                        table = f'Data from {start} to {end-timedelta(minutes=30)}\n[' + table
                        print(table)
                        print_table = False

                    if current != end_of_table:
                        ans = input('more?[y/n]:')
                        if config.data['readline']:
                            readline.remove_history_item(
                                readline.get_current_history_length()-1
                            )
                        if ans == 'y':
                            end = next_end(current)
                            print_table = True
                        elif ans == 'n':
                            break
                    else: 
                        break
            elif arg[1] == '-m':
                # calculate date one year later
                def next_end(current):
                    next_year = current.year+1
                    while current.year != next_year:
                        current += timedelta(days=1)
                    return current
                # read data from file
                try:
                    f = open('add_data/.remaining_gaps')
                    range_str_l = f.readlines()
                    # parse into datetime objects
                    range_l = []
                    for l in range_str_l:
                        l.strip('\n')
                        l2 = l.split()
                        range_l.append((datetime.fromisoformat(l2[0]), datetime.fromisoformat(l2[1])))
                    f.close()
                except FileNotFoundError:
                    range_l = []
                if len(range_l) > 0:
                    range_index = 0
                else:
                    range_index = None
                # values for start and end points
                start_index = 0
                char = (' ', '\033[31m+\033[0m', '\033[93mx\033[0m', '\033[32m@\033[0m') # characters used for printing with escape sequences for coloring
                start_of_table = entries[start_index][0].replace(month=1, day=1, hour=0, minute=0) # first day in month of start
                start_of_entries = entries[start_index][0] # date of first entry
                end_of_entries = entries[-1][0] # date of last entry
                end_of_table = next_end(end_of_entries).replace(month=1, day=1, hour=0, minute=0) # first day in month after end
                # preparations
                current = start_of_table
                end = next_end(start_of_table)
                empty = True # table starts with data that is not available
                index = start_index # index to track entries
                print_table = True
                while True:
                    table = ''
                    start = current # for information above table
                    while current != end:
                        stat = set()
                        for e in range(48):
                            if current == start_of_entries: # printing of available values and index counting starts
                                empty = False
                            if current == end_of_entries: # ends
                                empty = True
                            if empty == True: # printing if no data available
                                stat.add(0)
                            elif empty == False: # printing if data available
                                if entries[index][1]:
                                    stat.add(2)
                                else:
                                    if range_index != None:
                                        while entries[index][0] > range_l[range_index][1]:
                                            range_index += 1
                                            if range_index == len(range_l):
                                                range_index -= 1
                                                break
                                        if entries[index][0] >= range_l[range_index][0] and entries[index][0] <= range_l[range_index][1]:
                                            stat.add(0)
                                        else:
                                            stat.add(1)
                                    else: stat.add(1)
                            if empty == False:
                                index += 1
                            current += timedelta(minutes=30)
                        if stat in [{0}]: # if no data available
                                table += char[0]
                        elif stat in [{1}, {0, 1}]: # if 1 in set
                            table += char[1] # +
                        elif stat in [{1, 2}, {0, 1, 2}]: # if set is 1, 2 => extra char
                            table += char[2] # x
                        elif stat in [{2}, {0, 2}]: # if day contains 2 and 0 => complete
                            table += char[3] # @
                        if current.day == 1 and current.hour == 0 and current.minute == 0: # at line end
                            table += ']\n['
                    if print_table:
                        # assembling, cleaning and printing table
                        table = table.rstrip('\n[')
                        table = f'Data from {start} to {end-timedelta(minutes=30)}\n[' + table
                        print(table)
                        print_table = False

                    if current != end_of_table:
                        ans = input('more?[y/n]:')
                        if config.data['readline']:
                            readline.remove_history_item(
                                readline.get_current_history_length()-1
                            )
                        if ans == 'y':
                            end = next_end(current)
                            print_table = True
                        elif ans == 'n':
                            break
                    else: 
                        break
            else:
                print('\nUnknown option \'' + arg[1] + '\'!\n')
                s = 'Usage: database gaps OPTION\n'
                s += 'Options:\n'
                s += ' -d : temp gaps.\n'
                s += ' -m : temp gaps.\n'
                print(s)
        else:
            print('\nUnknown command \'' + arg[0] + '\'!\n')
            s = 'Usage: database COMMAND\n\n'
            s += 'Commands:\n'
            s += ' ping : check connection and try to reconnect if possible and necessary\n'
            s += ' mend : select download file\n'
            s += ' gaps : show gaps in database\n'
            print(s)

    def do_reqTimer(self, arg):
        '''Start or stop the request timer'''
        log = getLogger('REQUEST TIMER')
        global req_timer
        if arg == '':
            s = 'Usage: reqTimer OPTION\n\n'
            s += 'Options:\n'
            s += ' silent : hides request messages\n'
            s += ' show : shows request messages\n'
            s += ' start : Starts the request timer\n'
            s += ' stop : Stop the request timer\n\n'
            s += 'Current state: '
            if req_timer.run:
                s += 'running\n'
            else:
                s += 'stopped!\n'
            print(s)
        elif arg == 'silent':
            if not req_timer.msg:
                print('already silent')
            else:
                req_timer.msg = False
        elif arg == 'show':
            if req_timer.msg:
                print('already visible')
            else:
                req_timer.msg = True
        elif arg == 'start':
            if req_timer.run == False:
                req_timer.start()
                log.info('RequestTimer started')
                print('timer started!')
            else:
                print('timer has already been started!')
        elif arg == 'stop':
            req_timer.run = False
            log.info('RequestTimer stopped')
            print('timer stopped!')
        else:
            print('\nUnknown command \'' + arg[0] + '\'!\n')

    def do_config(self, arg):
        '''
        View and change the configuration values

        Attributes:
        -----------
        debug: bool
                change to show debug messages
        section_list: list
                list of all sections such as db, api1, ...
        exit_str: str
                input string that closes the config section
        back_str: str
                input string that returns to the previous view of the config section
        num_of_options: int
                number of options
        
        First-class functions:
        ----------------------
        section_selection():
                show sections and interpret the user input by calling section_match()
        key_selection(name_of_section: str):
                show keys and interpret the user input by calling key_match()
                only gets called, when the user gave a wrong input in section_match()
        value_selection(name_of_section: str, name_of_key: str):
                show value and interpret the user input by calling set_value()
         ---------
        section_match(inp: str):
                match the user input inp with the various section options
                if none matches, call section_selection()
        key_match(inp: str, name_of_section: str):
                match the user input inp with the various key options in section name_of_section
                in none matches, call key_selection()
        set_value(inp, name_of_section, name_of_key):
                rule out returning or exiting of user and call change_value()
         ---------
        change_value(new_value, name_of_section: str, name_of_key: str):
                change the value identified by name_of_section and name_of_key
                keep the datatype constant i.e. block user inputs that don't match it.
         ---------
        print_section_str():
                print list of sections
        print_key_str(name_of_section: str):
                print list of keys in a certain section
        print_value_str(name_of_key: str, name_of_section: str)
                print value with a certain key in a certain section
        '''
        #if some debug info is given while using the config command
        debug = False
        #start the first input request at the end of def so all defs are assigned
        section_list = list(config.data.keys())
        exit_str = "exit"
        back_str = "back"
        num_of_options = int(1)

        def section_selection():
            print_section_str()
            inp = input('> ')
            if config.data['readline']:
                # remove input from command history
                readline.remove_history_item(
                    readline.get_current_history_length()-1
                )
            section_match(inp)

        def key_selection(name_of_section: str):
            print_key_str(name_of_section)
            inp = input('> ')
            if config.data['readline']:
                # remove input from command history
                readline.remove_history_item(
                    readline.get_current_history_length()-1
                )
            key_match(inp, name_of_section)
        
        def value_selection(name_of_section: str, name_of_key: str):
            print_value_str(name_of_key,name_of_section)
            inp = input('> ')
            if config.data['readline']:
                # remove input from command history
                readline.remove_history_item(
                    readline.get_current_history_length()-1
                )
            set_value(inp, name_of_section, name_of_key)


        def section_match(inp: str):
            if debug: print("DEBUG: sectionMatch called, num_of_options: "+str(num_of_options))
            num = 0
            while num < num_of_options-2:
                #if exit_str then pass and break loop
                if inp == str(num_of_options) or inp == exit_str or inp == 'q':
                    break
                elif inp == str(num+1) or inp == section_list[num]:
                    #input was found and could be assigned to an section
                    #you will now get the selection with key you want to change
                    if debug: print("DEBUG: Success with: "+ str(num+1) + " or: "+ str(section_list[num]))
                    print_key_str(str(section_list[num]))
                    inp_ = input('> ')
                    if config.data['readline']:
                        # remove input from command history
                        readline.remove_history_item(
                            readline.get_current_history_length()-1
                        )
                    key_match(inp_, section_list[num])
                    break
                num += 1
            else:
                #when input couldn't be assigned to an section or exit. You will get the section selection again
                print("\nYou input was wrong. Chose from the list below or use the associated number.")
                section_selection()

        def key_match(inp: str, name_of_section: str):
            if debug: print("DEBUG: key_match called, num_of_options: "+str(num_of_options))
            key_list = list(config.data[name_of_section].keys())
            num = 0
            while num < num_of_options-2:
                #if exit_str than pass and break loop
                if inp == str(num_of_options) or inp == exit_str or inp == 'q':
                    break
                #if back_str than back to section selection and break loop
                if inp == str(num_of_options-1) or inp == back_str or inp == 'b':
                    section_selection()
                    break
                if inp == str(num+1) or inp == key_list[num]:
                    #input was found and could be assigned to an key
                    if debug: print("DEBUG: Success with: "+ str(num) + " or: "+ str(key_list[num]))
                    value_selection(name_of_section, str(key_list[num]))
                    break
                num += 1
            else:
                #when input couldn't be assigned to a section or exit. You will get the section selection again
                print("\nYou input was wrong. Chose from the list below or use the associated number.")
                key_selection(name_of_section)
        
        def set_value(inp, name_of_section, name_of_key):
            if debug: print("DEBUG: set_value called, num_of_options: "+str(num_of_options))
            #if exit_str then pass
            if inp == "2" or inp == exit_str or inp == 'q':
                return
            #if back_str then back to key selection
            if inp == "1" or inp == back_str or inp == 'b':
                key_selection(name_of_section)
                return
            #if not yet passed, change
            change_value(inp, name_of_section, name_of_key)


        def change_value(new_value, name_of_section: str, name_of_key: str):
            log = getLogger('CONFIG')
            if debug: print("DEBUG: change_value called, new_value: "+str(new_value))
            if type(config.data[name_of_section][name_of_key]) == int:
                try:
                    config.data[name_of_section][name_of_key] = int(new_value)
                    log.info(f'value {name_of_key} in section {name_of_section} changed to int {new_value}')
                except:
                    print("\nThe value couldn't be changed because to type must be a Number!")
                    value_selection(name_of_section, name_of_key)
                    return
            elif type(config.data[name_of_section][name_of_key]) == bool:
                try:
                    config.data[name_of_section][name_of_key] = bool(new_value)
                    log.info(f'value {name_of_key} in section {name_of_section} changed to bool {new_value}')
                except:
                    print("\nThe value couldn't be changed because to type must be a Boolean!")
                    value_selection(name_of_section, name_of_key)
                    return
            else:
                config.data[name_of_section][name_of_key] = str(new_value)
                log.info(f'value {name_of_key} in section {name_of_section} changed to str {new_value}')

            print("\nChanged to: "+str(new_value))
            key_selection(name_of_section)


        def print_section_str():
            #returns a string with a list of all sections from the config + exit
            out_str = "\nIn which section of the config is the value you want to change?\n"
            num = 0
            option_num = len(section_list)
            while num < option_num:
                out_str += str(num+1) + " => " + section_list[num] + "\n"
                num += 1
            out_str += str(num+1) + " => " + exit_str + "\n"
            print(out_str, end='')
            nonlocal num_of_options
            num_of_options = num+1
        
        def print_key_str(name_of_section: str):
            #gets a list of all keys in the chosen section
            key_list = list(config.data[name_of_section].keys())
            #returns a string with a list of all kes from to chosen section from the config + exit and back
            out_str = "\nIn witch key of the section is the value you want to change?\n"
            num = 0
            option_num = len(key_list)
            while num < option_num:
                out_str += str(num+1) + " => " + key_list[num] + " :"+str(config.data[name_of_section][str(key_list[num])]) + "\n"
                num += 1
            else:
                out_str += str(num+1) + " => " + back_str + "\n"
                num += 1
                out_str += str(num+1) + " => " + exit_str + "\n"
            print(out_str, end='')
            nonlocal num_of_options
            num_of_options = (num+1)

        def print_value_str(name_of_key: str, name_of_section: str):
            out_str = "\nIf the input isn't an option from below, '"+str(name_of_key)+":"+str(config.data[name_of_section][name_of_key])+"' will be changed to the input.\n"
            out_str += "1 => " + back_str + "\n"
            out_str += "2 => " + exit_str + "\n"
            num_of_options == 2
            print(out_str, end='')

        #start the interface with the section selection
        section_selection()

    def do_debug(self, arg):
        '''Provides different debug functionalities'''
        log = getLogger('DEBUG ACTIONS')
        if arg == 'add':
            time = time_utils.get_now(string=True)
            log.info('starting debug request')
            req_timer.make_req(time, debug=True)
        elif arg == 'dAdd':
            req_timer.trigger_debug_request = True
            log.debug('debug action triggered')
            print('trigger: ' + str(req_timer.trigger_debug_request))
        elif arg == 'rm':
            log.info('removing last line')
            try:
                db.rm_last()
            except DBWritingError:
                log.error('DBWritingError')
                print('--> line could not be removed!')
            except DBTimeoutError:
                log.error('DBTimeoutError')
                print("Database didn't respond!")
            else:
                log.info('line removed')
                print('--> line removed')
        elif arg == 'reqApi1':
            try:
                dt = datetime.now()
                times = dt.strftime('%Y.%m.%d_%H:%M:%S')
                name = f'api1_{times}.json'
                f = open('requests/' + name, mode='x')
                json.dump(api1.request(), f, indent='\t')
            except FileExistsError:
                print('You cant send requests multiple times per second!')
            except ApiConnectionError:
                print('Connection to Api1 failed!')
            except ApiTimeoutError:
                print("Api didn't respond!")
            else:
                print(f'file {name} created')
        elif arg == 'reqApi2':
            try:
                dt = datetime.now()
                times = dt.strftime('%Y.%m.%d_%H:%M:%S')
                name = f'api2_{times}.json'
                f = open('requests/' + name, mode='x')
                json.dump(api2.request(), f, indent='\t')
            except FileExistsError as e:
                print('You cant send requests multiple times per second!')
            except ApiConnectionError:
                print('Connection to Api2 failed!')
            except ApiTimeoutError:
                print("Api didn't respond!")
            else:
                print(f'file {name} created')
        elif arg == 'sendMail':
            log.debug('calling debug_email()')
            emailMessages.debug_email()
        else:
            s = '\nUnknown command \'' + arg + '\' Usage: debug COMMAND\n\n'
            s += 'Commands:\n'
            s += ' add : Adds row to db with current weather data.\n'
            s += ' dAdd : like \'add\' but called by the thread of req_timer.\n'
            s += ' rm : Remove last row of db.\n'
            s += ' reqApi1 : Send a request to API1 and save the answer as .json file in requests/\n'
            s += ' reqApi2 : Send a request to API2 and save the answer as .json file in requests/\n'
            s += ' sendMail : Call the debug_email() function in emailMessages.py\n'
            print(s)

    def do_restart(self, arg):
        '''Restart program and keep the cmd history.'''
        restart()

    def do_quit(self, arg):
        '''Exit program.'''
        quit()

def restart():
    '''Save the cmd history, the configuration and call itself'''
    log = getLogger('RESTART')
    log.info('stopping RequestTimer')
    req_timer.run = False
    log.debug('writing cmd history')
    if config.data['readline']:
        readline.write_history_file('.cmd_history')
    log.info('saving config data')
    config.save()
    path = f'"{os.path.abspath(__file__)}"'
    log.info('restart')
    os.execl(sys.executable, path, sys.argv[0], 'restart') # executes in the command line to call itself

def quit():
    '''Save the configuration and exit the program'''
    log = getLogger('SHUTDOWN')
    log.info('stopping RequestTimer')
    req_timer.run = False
    log.info('saving config data')
    config.save()
    log.info('shutdown')
    sys.exit()

if __name__ == '__main__':
    if ['-d', '--debug'] in sys.argv:
        debugging = True
    else:
        debugging = False

    time_utils = TimeUtils()
    config = Configuration()
    config.init_logging()

    db = None
    api1 = None
    api2 = None
    req_timer = None

    cli = CLI()
    if config.data['readline']:
        import readline

        # load command history
        if 'restart' in sys.argv:
            readline.read_history_file('.cmd_history')

        # enables autocompletion depending on the system MacOS/Linux or Windows
        if os.name == 'posix':
            readline.parse_and_bind('bind ^I rl_complete')
        else:
            readline.parse_and_bind('tab: complete')
    cli.cmdloop()

