#!/usr/bin/python

import Pyro4
import syslog
import signal
import os
import imp
import multiprocessing
from multiprocessing import Process, Value
import MySQLdb as mysql
import sys
import json
from setproctitle import setproctitle #pip install setproctitle
from plexus.BackupTask import BackupTask

CONFIG_FILE = '/etc/unimatrix/zero.conf'
# we use multiplex, rather than threading, cos each request only starts a
# new worker process or simply returning status information. the threaded 
# model would work fine, its just it means handling locking in python,
# and it means the GIL, so... no thx.
Pyro4.config.SERVERTYPE = "multiplex"
Pyro4.config.SOCK_REUSE = True	

class PlexusDaemon(object):

	debug = False
	db    = None
	pyro  = None

	## PRIVATE METHODS #########################################################

	def __init__(self, pyro):
		syslog.openlog("plexus", syslog.LOG_PID)

		## rename the process title
		setproctitle("plexus")

		## Load the config and drop privs
		self._load_config(CONFIG_FILE)

		## Store the copy of the pyro daemon object
		self.pyro = pyro

		## Set up signal handlers
		signal.signal(signal.SIGTERM, self._signal_handler_term)
		signal.signal(signal.SIGINT, self._signal_handler_int)

		## preload a connection to mysql
		self._get_db()

	def _signal_handler_term(self, signal, frame):
		self._signal_handler('SIGTERM')
	
	def _signal_handler_int(self, signal, frame):
		self._signal_handler('SIGINT')
	
	def _signal_handler(self, signal):
		syslog.syslog('caught signal ' + str(signal) + "; exiting")
		Pyro4.core.Daemon.shutdown(self.pyro)
		sys.exit(0)

	def _get_cursor(self):
		self._get_db()
		return self.db.cursor(mysql.cursors.DictCursor)

	def _get_db(self):
		if self.db:
			if self.db.open:
				try:
					curd = self.db.cursor(mysql.cursors.DictCursor)
					curd.execute('SELECT 1')
					result = curd.fetchone();

					if result:
						return self.db

				except (AttributeError, mysql.OperationalError):
					syslog.syslog("MySQL connection is closed, will attempt reconnect")

		## If we didn't return up above then we need to connect first
		return self._db_connect()
		
	def _db_connect(self):
		syslog.syslog("Attempting connection to MySQL")
		self.db = mysql.connect(self.config['MYSQL_HOST'], self.config['MYSQL_USER'], self.config['MYSQL_PASS'], self.config['MYSQL_NAME'], charset='utf8')
		curd = self.db.cursor(mysql.cursors.DictCursor)
		curd.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED")
		syslog.syslog("Connection to MySQL established")
		return self.db

	def _load_config(self, filename): 
		d = imp.new_module('config')
		d.__file__ = filename
		try:
			with open(filename) as config_file:
				exec(compile(config_file.read(), filename, 'exec'), d.__dict__)
		except IOError as e:
			syslog.syslog('Unable to load configuration file (%s)' % e.strerror)
			sys.exit(1)
		self.config = {}
		for key in dir(d):
			if key.isupper():
				self.config[key] = getattr(d, key)

		## ensure we have required config options
		for wkey in ['PLEXUS_KEY', 'MYSQL_HOST', 'MYSQL_USER', 'MYSQL_PASS', 'MYSQL_NAME']:
			if not wkey in self.config.keys():
				print "Missing configuation option: " + wkey
				sys.exit(1)

		if 'DEBUG' in self.config.keys():
			if self.config['DEBUG'] == True:
				self.debug = True
				
		return True

	## This is called on each pyro loop timeout/run to make sure defunct processes
	## (finished tasks waiting for us to reap them) are reaped
	def _onloop(self):
		multiprocessing.active_children()
		return True

	## RPC METHODS #############################################################

	@Pyro4.expose
	def ping(self):
		return True

	## List active backup jobs
	@Pyro4.expose
	def active_tasks(self):
		active_processes = multiprocessing.active_children()
		active_tasks = []
		for proc in active_processes:
			proc_data = json.loads(proc.name)
			active_tasks.append(proc_data)

		return active_tasks
	
	@Pyro4.expose
	def request_backup(self,name):
		curd = self._get_cursor()

		## Check name is valid in database
		curd.execute("SELECT * FROM `systems` WHERE `name` = %s", (name,))
		system = curd.fetchone()

		if system is None:
			raise Exception("No system was found in the database matching that name")	

		## Check a backup isn't already in progress
		tasks = self.active_tasks()
		for task in tasks:
			if int(task['sid']) == int(system['id']):
				raise Exception("A backup is already in progress for the system")

		try:
			## Record the job in MySQL
			curd.execute("INSERT INTO `tasks` (`sid`, `name`, `start`) VALUES (%s, 'backup', NOW())", (system['id'],))
			self.db.commit()
			task_id = curd.lastrowid
		except Exception as ex:
			raise Exception("Could not record task in the database: " + str(type(ex)) + " " + str(ex))

		## Start the job
		backup_task = BackupTask(task_id, system, self.config)
		task        = Process(target=backup_task.run, name=json.dumps({'id': task_id, 'sid': system['id'], 'name': 'backup'}))
		task.start()

		syslog.syslog('started backup task for ' + system['name'] + ' with task id ' + str(task_id) + ' and worker pid ' + str(task.pid))
		
		return task_id

	@Pyro4.expose
	def is_backup_running(self,task_id):
		curd = self._get_cursor()

		## Check name is valid in database
		curd.execute("SELECT * FROM `tasks` WHERE `id` = %s", (task_id,))
		task = curd.fetchone()

		if task is None:
			raise Exception("No such backup task was found")	

		# If the task has been marked in the DB, then no it finished
		if task['status'] != 0:
			return False

		## Check the task is actually still running still
		tasks = self.active_tasks()
		for task in tasks:
			if int(task['id']) == int(task['id']):
				return True
		
		return False
