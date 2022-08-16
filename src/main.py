from customExceptions import *
import sys, os, time  # System
# For names of request files and RequestTimer
from datetime import datetime, timedelta, tzinfo
import email.utils # for conversion of rfc822 to datetime
from threading import Thread  # For RequestTimer
import hmac  # Hash function for WeatherLink-API
import pymysql, requests, json#, eventlet  # APIs and database
import cmd, readline  # Command line
import csv  # Read download-files

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
		f = open('../rsc/config.json')
		configs = f.read()
		self.data = json.loads(configs)
		f.close()

	def save(self):
		'''Save the content of "data" in the config.json file.'''
		configfile = open('../rsc/config.json', 'w')
		json.dump(self.data, configfile, indent='\t')
		configfile.close()
			
	# def database_msg(self, prev_text='', optn=None):
	# 	s = prev_text

	# 	if not optn:
	# 		s += ' Connection with database:'
	# 		if not self.database_check:
	# 			s += f' failed!\n  {sc.database["error"]}\n'\
	# 			f'{cli.print_iterable(config.data["dbLogin"], indent="   ")}'\
	# 			'  Database may not be active or the login data is incorrect!\n'\
	# 			'  Use "config dbLogin" to change login data and reconnect\n'
	# 		else:
	# 			s += ' established\n'
	# 		return s

	# def api1_msg(self, prev_text='', optn=None):
	# 	s = prev_text

	# 	if not optn:
	# 		s += ' API1 Connection:'
	# 		if not self.api1_check:
	# 			s += ' failed!\n'
	# 			s += '  Make sure, the connection to the internet is working!\n'
	# 			s += '  It could also be that the API is offline.\n'
	# 			return s
	# 		s += ' established\n'
	# 		s += f'  Size of response: {self.api1["resp_size"]} bytes\n'
	# 		return s

	# def api2_msg(self, prev_text='', optn=None):
	# 	s = prev_text

	# 	if not optn:
	# 		if not self.api1_check:
	# 			return s
	# 		s += ' API2 Connection:'
	# 		if self.api1_check:
	# 			s += ' established'
	# 		else:
	# 			s += ' failed'
	# 		s += ' (not used)\n\n'
	# 		return s

	# def requestTimer_msg(self, prev_text='', optn=None):
	# 	s = prev_text

	# 	if not optn:
	# 		if not self.requestTimer['values']:
	# 			s += ' Values could not be extracted from API1 response!\n\n'
	# 			return s

	# 		v = self.requestTimer['values']

	# 		s += ' Values extracted:\n'
	# 		s += '  temp | pressure | hum | windspeed | winddir | rainrate | uvindex\n'
	# 		s += f'  {v[1]} | {v[2]}   | {v[3]}  | {v[4]}       | {v[5]}     | {v[6]}      | {v[7]}\n'
	# 		s += '\n'

	# 		s += ' Writing to the database:'
	# 		if not self.requestTimer['writing_to_db']:
	# 			s += ' failed!\n\n'
	# 			return s
	# 		s += ' successful\n\n'

	# 		if self.requestTimer['timer_counting']:
	# 			s += ' Request timer: started\n'
	# 			s += f'  next request in {self.requestTimer["timer_counting"]} seconds\n'
				
	# 	return s

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
	est : bool
			indicates if connection is successfully made
	error : pymysql.err.OperationalError
			the error that occurs when the connection does not work 
			If there is no error, it is None.
	cursor : pymysql.cursors.DictCursor
			cursor object for database
	row_count : int
			number of rows in the db

	Methods
	-------
	connect():
			Tries to establish the connection with the db
	ping():
			Checks the connection with a ping and changes the attributes accordingly.
	get_gaps():  * * * under construction * * *
			Reads the content of the db and finds the gaps, where data is missing.
	add_row(values):
			Adds a line at the end of the db with the data from "values".
	insert_row()  * * * under construction * * *
			Not yet implemented, but should add a row and then sort the lines (for filling gaps).
	rm_last():
			Removes the last entry.
	check():
			Returns variables for SystemCheck
	'''

	def __init__(self):
		self.config = config.data['dbLogin']

	def check(self):
		self.connect()
		self.add_row(
			['2022-08-13 13:25:00',
			'26.9',
			'1014.7',
			'39',
			'1.60934',
			'SO',
			'0.0',
			'2.2']
			)
		self.rm_last()

	def connect(self):
		'''Try to connect with the mysql database.'''
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

	def ping(self, reconnect=False):
		if not self.con:
			self.connect()
		# add timeout
		def ping():
			try:
				self.con.ping(reconnect=reconnect)
				return True, None
			except pymysql.err.OperationalError as e:
				return None, DBConnectionError(e)
		timeout = TimeoutHelper(ping)
		timeout.timer(self.config['timeoutMs'], DBTimeoutError)

	def add_row(self, values):
		'''Add a row to the db with the values from "values"'''
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
		timeout = TimeoutHelper(exec)
		# this starts the thread with con() and a timer
		# finishes the timer before the function is executed, a timeout error is raised
		timeout.timer(self.config['timeoutMs'], DBTimeoutError)

	def rm_last(self):
		'''Remove last row in the "weatherdata" table'''
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
			unique API-Token. Dont share with anyone!
			If compromised generate a new one at https://www.weatherlink.com/account
	 --- SystemCheck ---
	con : bool
			true if request did not throw an exception
	data_parsed : bool
			true if parsing the response to dict did not throw an exception
	resp_size
			the size of the response object in bytes

	Methods
	-------
	request():
			Makes an HTTP request with the given values. 
			Returns the answer in json format as dict
	check():
			Returns variables for SystemCheck
	'''

	def __init__(self):
		self.config = config.data['weatherlinkApi']
		self.url = self.config['url']
		self.user = self.config['user']
		self.password = self.config['pass']
		self.token = self.config['apiToken']

	def check(self):
		# check for functionality
		self.get_values()

	def request(self):
		'''Return response from the Api as a dict.'''
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

		Parameters
		----------
		time : str
				overwrites the entryDate value in vlist
		'''
		if not time:
			time = req_timer.get_now(string=True)
		# request Api1
		data = self.request()

		# check if data is up to date
		datestr = data['observation_time_rfc822']
		datet = email.utils.parsedate_to_datetime(datestr)
		datet = datet.replace(hour=datet.hour-1, tzinfo=None)
		now = req_timer.get_now()
		deltat = now - datet
		if deltat > timedelta(minutes= self.config['dataMaxAge']):
			raise WStOfflineError(datet)

		vlist = {}
		# date
		vlist['time'] = time

		error = None
		try:
			# temp
			vlist['temp'] = data['temp_c']

			# pressure
			vlist['pressure'] = data['pressure_mb']

			# hum
			vlist['hum'] = data['relative_humidity']

			# wind_speed
			in_kmh = float(data['wind_mph'])
			in_kmh *= 1.60934
			vlist['wind_speed'] = str(in_kmh)

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

			# rain_rate_per_hr
			in_mm = float(data['davis_current_observation']
					  ['rain_rate_in_per_hr']) * 25.4
			vlist['rain_rate_per_hr'] = str(in_mm)

			# uv_index
			vlist['uv_index'] = data['davis_current_observation']['uv_index']
		except KeyError as e:
			if not error:
				error = DataIncompleteError()
			error.missing.append(e.args[0])
		if error: raise error

		return list(vlist.values())

class Api2:
	'''
	A class to represent the API V2

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
			used to calculate the signature for the request Dont share with anyone! 
			If compromised generate a new one at https://www.weatherlink.com/account
	station_id : str
			ID which identifies the weather station the data is requested from
	 --- SystemCheck ---
	con : bool
			true if request did not throw an exception
	data_parsed : bool
			true if parsing the response to dict did not throw an exception
	resp_size
			the size of the response object in bytes

	Methods
	-------
	request():
			Makes an HTTP request with the values and the calculated signature.
	get_stations():
			Makes an HTTP request to get all the possible station IDs and returns the answer in a compact format.
	check():
			Returns variables for SystemCheck
	'''

	def __init__(self):
		self.config = config.data['weatherlinkApi2']
		self.url = self.config['url']
		self.key = self.config['api-key']
		self.secret = self.config['api-secret']
		self.station_id = self.config['stationID']
	
	def check(self):
		# check for functionality
		self.request()

	def request(self):
		'''Return dict from Api2 http request.'''
		t = int(time.time())
		paramstr = f'api-key{self.key}station-id{self.station_id}t{t}'
		hmac_obj = hmac.new(str.encode(self.secret),
							str.encode(paramstr), 'sha256')
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
		'''Return IDs and names from weatherlink Stations as dict'''
		t = int(time.time())
		paramstr = f'api-key{self.key}t{t}'
		hmac_obj = hmac.new(str.encode(self.secret),
							str.encode(paramstr), 'sha256')
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
	'''A class that periodically loads data into the database

	Attributes
	----------
	config : dict
			configuration data for requestTimer
	show_msg : bool
			determines if a message is shown when a line is added to the database
	run : bool
			defaults to true. Is used to stop the timer thread
	timer_count : int
			synchronized with the counting variable in timer()
	values : list
			list of values returned by get_values()
	next_req : datetime
			time when the next line will be added to the database
	seconds_till_next : int
			number of seconds till next_req. Used by timer()
	thread : Thread
			thread for the timer
	row_dif : bool
			is true, if the count of affected rows in the db changes
			checked make_req()

	Methods
	-------
	start():
			Creates thread for the timer and starts it.
	timer():
			Counts down seconds_till_next and calls make_req().
	make_req(time=None):
			Makes request and adds row to the database.
	get_now():
			returns datetime object of CET timezone
	get_next_req_time():
			Calculates next_req.
	get_values(time):
			Makes API1 request and creates list with selected values.
	line_msg(time, vlist):
			Builds message for when a line is added to the database
	check():
			Returns variables for SystemCheck
	'''

	def __init__(self):
		# configuration
		self.config = config.data['requestTimer']
		self.show_msg = self.config['show_message']

	def start(self):
		'''Initiate thread with timer().'''
		self.next_req = self.get_next_req_time()
		self.seconds_till_next = (self.next_req-self.get_now()).seconds

		self.thread = Thread(name='timer', target=self.timer, daemon=True)
		self.thread.start()

	def timer(self):
		'''Times requests.'''
		i = self.seconds_till_next + 1
		self.run = True
		while self.run:
			if i > 0:
				time.sleep(1)
				i -= 1
			else:
				self.make_req()
				# calculate next request
				self.next_req = self.get_next_req_time()
				self.seconds_till_next = (self.next_req-self.get_now()).seconds
				i = self.seconds_till_next + 1

	def make_req(self, time=None, msg=True, debug=False):
		'''Get values from get_values() and add them to the database.

		Trigger message if show_msg is true.
		Calculate next_req and seconds_till_next

		Parameters
		----------
		time : str
				determines the date value in vlist
		debug : bool
				gets passed on to line_msg()
		'''
		if time == None:
			time = self.next_req.isoformat(sep=' ')

		try:
			db.ping(reconnect=True)
		except DBConnectionError:
			pass
		except DBTimeoutError:
			pass

		try:
			# get Values
			values = api1.get_values(time)
		except BaseException as e:
			if isinstance(e, ApiConnectionError):
				print(f'--> {time} - Connection with Api1 failed!')
			elif isinstance(e, DataIncompleteError):
				print(f'--> {time} - Data of request is incomplete!')
				print(' missing Data:')
				s = cli.print_iterable(e.missing, indent=' - ')
				print(s)
			elif isinstance(e, WStOfflineError):
				print(f'--> {time} - Data of request is outdated!')
			elif isinstance(e, ApiTimeoutError):
				print(f'--> {time} - The request timed out!')
			else: raise e
		else:
			try:
				# add row to db
				db.add_row(values) # try
			except BaseException as e:
				if isinstance(e, DBConnectionError):
					print(f'--> {time} - Connection with db failed!')
				elif isinstance(e, DBWritingError):
					print(f'--> {time} - Writing to db failed!')
				elif isinstance(e, DBTimeoutError):
					print(f"--> {time} - The db didn't respond!")
				else: raise e
			else:
				# message
				if self.show_msg and msg:
					self.line_msg(time, values, debug=debug)


	def get_now(self, string=False):
		now = datetime.utcnow() + timedelta(hours=1)  # uses CET, ignores DTS
		now = now.replace(microsecond=0)
		if string:
			return now.isoformat(sep=' ')
		return now

	def get_next_req_time(self):
		'''Calculate time of next request.

		Requests are always at xx:00 or at xx:30
		'''
		now = self.get_now()
		next_req = now + timedelta(minutes=30)
		minutes = next_req.minute
		if minutes < 30:
			next_req = next_req.replace(minute=0, second=0, microsecond=0)
		else:
			next_req = next_req.replace(minute=30, second=0, microsecond=0)
		return next_req

	def line_msg(self, time, values, debug=False):
		'''Build message for when a new line is added to the database.

		Parameters
		----------
		time : str
				sting that shows when the request was made
		vlist : list
				list with values from the request
		row_d : int
				difference in rows of the db before and after the new row was added
		debug : bool
				determines weather or not the cli prompt is printed and if new lines are added or not
		'''
		if debug:
			msg = ''
		else:
			msg = '\n'
		# entry time
		msg += f'--> {time} - '
		# list of values
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
	intro : str
			intro message built by preloop()

	Methods
	-------
	connection_msg():
			Returns message string which shows if the database is successfully connected or not.
	ping_msg():
			Returns message string which shows if database is already connected, reconnected or not connected.
	preeloop():
			Runs before cmdloop() starts. Shows if all parts of the program work.
	default(line):
			Gets executed if command is unknown.
	emptyline():
			Gets executed if empty command is entered.
	 --- string utilities ---
	print_iterable(i):
			Returns string of iterable object i depending on the type.
	check_time_syntax(s):
			Returns True or False depending on whether the syntax for a requestTimes entry is correct.
			(This function is obsolete, because the RequestTimer class does not use it.)
	 --- commands ---
	do_reconnect(arg):
			Try to reconnect with the database.
	do_request(arg):
			Save answer of API1 or API2 request as .json file in "requests".
	do_loadDownloadFiles(arg):
			• • • under construction • • •
	do_config(arg):
			View and change configuration.
	do_debug(arg):
			Provides different debug functionalities.
	do_restart(arg):
			Restart program and keep the cmd history.
	do_quit(arg):
			Exit program.
	'''
	prompt = '---(DB-Manager)> '

	def ping_msg(self):
		'''Build message depending on wether the connection is already established,
		established or not established.'''
		if db.est:
			s = 'connection is already established!'
		else:
			s = 'connection lost!\n\n'
			s += self.connection_msg()
		return s

	def preloop(self):
		'''Check if different parts of the program are working and build intro message.'''

		s = '    -- DB-Manager --\n\n'

		# requestTimer
		global req_timer
		req_timer = RequestTimer()
		start_req_timer = True

		# api1
		global api1
		api1 = Api1()
		s += ' API1 request:'
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

		# api2 (not used)
		global api2
		s += ' API2 request:'
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

		# database
		global db
		db = Database()
		s += ' Connection with database:'
		try:
			db.check()
		except BaseException as e:
			# msg in chat
			s += ' failed!\n'
			if isinstance(e, DBConnectionError):
				s += f'{cli.print_iterable(config.data["dbLogin"], indent="   ")}'
				s += '  Database may not be active or the login data is incorrect!\n'
				s += '  Use "config dbLogin" to change login data and reconnect\n\n'
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

		if start_req_timer:
			req_timer.start()
			# msg in chat
			s += '  Everything is ok:\n'
			s += '   Request timer started.\n\n'
		else:
			s += "  Request timer didn't start!\n\n"

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

	def check_time_syntax(self, s):
		'Check the syntax of a requestTimes value\n\n'\
			'Syntax: hh:mm , "x" stands for any digit'
		ls = list(s)
		if len(ls) != 5:
			return False
		else:
			for i, char in enumerate(ls):
				if i == 2 and char == ':':
					pass
				elif char.isnumeric() or char == 'x':
					pass
				else:
					return False
			return True

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
			except FileExistsError as e:
				print('You cant send requests multiple times per second!')
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
			else:
				print(f'file {name} created')

	def do_loadDownloadFiles(self, arg):
		path = '../add_data_to_db/'
		file_list = os.listdir(path)
		dfiles = []
		for i, e in enumerate(file_list):
			if os.path.isfile(path + e) and e.startswith('') and e.endswith('.csv'):
				dfiles.append(e)

		for e in dfiles:
			print(e)

	def do_config(self, arg):
		'''View and change configuration'''
		# messages
		def usage_and_sections_msg(liststr): return 'Usage: config SECTION [KEY VALUE|add VALUE|rm VALUE]\n\n'\
			'Show and change configuration values\n\n'\
			'sections:\n' + liststr
		def list_usage_msg(
			section): return f'Usage: config {section} [add VALUE|rm VALUE]\n'
		def dict_usage_msg(
			section): return f'Usage: config {section} [KEY VALUE]\n'
		def type_not_supported_msg(section): return f'{section} is a {type(section)}!\n'\
			'This type is not supported, please change the configfile'
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
		if arg == '':
			s = 'Usage: debug COMMAND\n\n'
			s += 'Commands:\n'
			s += ' add : Adds row to db with current weather data.\n'
			s += ' rm : Remove last row of db.\n'
			print(s)
		elif arg == 'add':
			time = req_timer.get_now(string=True)
			req_timer.make_req(time, debug=True)
		elif arg == 'rm':
			db.rm_last()
			print('--> line removed!')
		elif arg == 'ping':
			print(db.con.ping())

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
	os.execl(sys.executable, 'python3', __file__, 'restart')

def quit():
	'''Exit the program'''
	req_timer.run = False
	config.save()
	sys.exit()

if __name__ == '__main__':
	if 'restart' in sys.argv:
		readline.read_history_file('.cmd_history')

	config = Configuration()

	db = None
	api1 = None
	api2 = None
	dl = None
	req_timer = None

	cli = CLI()
	if os.name == 'posix':
		readline.parse_and_bind('bind ^I rl_complete')
	else:
		readline.parse_and_bind('tab: complete')
	cli.cmdloop()

	# dl = Download()
	# dl.load('_1-3-22_00-00_1_Day_1647772733_v2.csv')