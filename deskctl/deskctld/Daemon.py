#!/usr/bin/python

import Pyro4
import syslog
import signal
import os
import sys
import json
from setproctitle import setproctitle #pip install setproctitle
import subprocess
import yum
import multiprocessing
from multiprocessing import Process
import traceback
import pwd
import sqlite3
import logging

Pyro4.config.SERVERTYPE = "multiplex"
Pyro4.config.SOCK_REUSE = True

################################################################################

def set_socket_permissions(socket_path):
	## set perms on the socket path
	try:
		os.chown(socket_path,0,800001)
	except Exception as ex:
		sys.stderr.write("Could not chown socket: " + str(type(ex)) + " " + str(ex))
		sys.exit(1)

	try:
		os.chmod(socket_path,0770)
	except Exception as ex:
		sys.stderr.write("Could not chmod socket: " + str(type(ex)) + " " + str(ex))
		sys.exit(1)

################################################################################

class DeskCtlDaemon(object):

	allowed_groups = ['sys','users','wheel','vboxusers']
	pkgTaskQueue   = []
	pkgTaskCurrent = None
	pkgProcess     = None

	## PRIVATE METHODS #########################################################

	def __init__(self, pyro):
		syslog.openlog("deskctld", syslog.LOG_PID)

		## rename the process title
		setproctitle("deskctld")

		## Store the copy of the pyro daemon object
		self.pyro = pyro

		## Set up signal handlers
		signal.signal(signal.SIGTERM, self._signal_handler_master)
		signal.signal(signal.SIGINT, self._signal_handler_master)

		syslog.syslog('deskctld started')

	def _signal_handler_master(self, sig, frame):
		if sig == signal.SIGTERM: 
			sig = "SIGTERM"
		elif sig == signal.SIGINT:
			sig = "SIGINT"

		syslog.syslog('master process caught ' + str(sig) + "; exiting")
		Pyro4.core.Daemon.shutdown(self.pyro)
		multiprocessing.active_children()
		sys.exit(0)

	def _signal_handler_child(self, sig, frame):
		if sig == signal.SIGTERM: 
			sig = "SIGTERM"
		elif sig == signal.SIGINT:
			sig = "SIGINT"

		syslog.syslog('pkg process caught ' + str(sig) + "; exiting")
		sys.exit(0)

	## This is called on each pyro loop timeout/run to make sure defunct processes
	## (finished tasks waiting for us to reap them) are reaped and to start
	## a new package process if there is a task in the queue
	def _onloop(self):
		multiprocessing.active_children()

		if len(self.pkgTaskQueue) > 0:
			if self.pkgProcess is not None: # this should never happen, but we'll check anyway
				if not self.pkgProcess.is_alive():
					self.startPackageTask(self.pkgTaskQueue.pop(0))

		return True

	def sysexec(self,command,shell=False,env={}):
		try:
			procenv = os.environ.copy()
			for key, value in env.iteritems():
				procenv[key] = value

			proc = subprocess.Popen(command,stdout=subprocess.PIPE, stderr=subprocess.STDOUT,shell=shell,env=procenv)
			(stdoutdata, stderrdata) = proc.communicate()
			if stdoutdata is None:
				stdoutdata = ""

			return (proc.returncode,str(stdoutdata))
		except Exception as ex:
			return (1,str(type(ex)) + " " + str(ex))

	def pkgProcessTask(self,task):
		setproctitle("deskctld-pkg")
		syslog.openlog("deskctld-pkg", syslog.LOG_PID)
		signal.signal(signal.SIGTERM, self._signal_handler_child)
		signal.signal(signal.SIGINT, self._signal_handler_child)
		syslog.syslog('deskctld-pkg started')

		## open the pkgdb sqlite database
		try:
			conn = sqlite3.connect("/etc/soton/pkgdb.sqlite")
			conn.row_factory = sqlite3.Row
			cursor = conn.cursor()
		except Exception as ex:
			syslog.syslog("Could not open the pkgdb: " + str(type(ex)) + " - " + str(ex))
			return

		if task['action'] in ['install','remove']:
			# try to load the package data from the pkgdb by ID
			cursor.execute("SELECT * FROM `entries` WHERE `id` = ?",(task['id'],))
			entry = cursor.fetchone()

			if entry is None:
				syslog.syslog("Could not find requested entry ID " + task['id'])
				return

			try:
				yb=yum.YumBase()
				yb.conf.cache = 0
				logger = logging.getLogger("yum.verbose.YumPlugins")
				logger.setLevel(logging.CRITICAL)

				## Now we need to get the individual packages or groups
				## which make up this 'entry'.
				cursor.execute("SELECT * FROM `items` WHERE `entry` = ?",(task['id'],))
				items = cursor.fetchall()

				transaction = False
				for item in items:
					# start of loop over each item

					# Check if we've been asked to install a package group
					if item['name'].startswith("@"):
						group = True
						item_name = item['name'][1:]
						item_type = "group"
					else:
						group = False
						item_name = item['name']
						item_type = "package"

					## support name.arch if not a package group
					if not group:
						arch=None
						if item_name.endswith(".i686"):
							item_name = item_name[:-5]
							arch = "i686"
						elif item_name.endswith(".x86_64"):
							item_name = item_name[:-7]
							arch = "x86_64"
						elif item_name.endswith(".noarch"):
							item_name = item_name[:-7]
							arch = "noarch"

						# If we've been told to install
						if task['action'] == 'install':
							try:
								res = yb.install(name=item_name,arch=arch,silence_warnings=True)
							except Exception as ex:
								syslog.syslog("Could not install package " + item_name + ": " + str(ex))
								continue

						elif task['action'] == 'remove':
							try:
								res = yb.remove(name=item_name,arch=arch,silence_warnings=True)
							except Exception as ex:
								syslog.syslog("Could not remove package " + item_name + ": " + str(ex))
								continue
					else:
						# this is a group action, not a package
						if task['action'] == 'install':
							try:
								res = yb.selectGroup(grpid=item_name)
							except Exception as ex:
								syslog.syslog("Could not install group " + item_name + ": " + str(ex))
								continue

						elif task['action'] == 'remove':
							try:
								res = yb.groupRemove(grpid=item_name)
							except Exception as ex:
								syslog.syslog("Could not remove group " + item_name + ": " + str(ex))
								continue

					if len(res) > 0:
						transaction = True
					else:
						# this means that yum returned no transaction results (it doesnt, sadly, return
						# an exception with any useful information. So we just know that yum couldn't
						# do anything...cos we got nothing in the 'res' list. Oh well.
						syslog.syslog("Could not " + task['action'] + " " + item_type + " " + item_name)

					## end of loop over each item

				# did we find any actions to undertake?
				if transaction:
					syslog.syslog("running transaction check")
					yb.buildTransaction()
					syslog.syslog("processing transaction")
					yb.processTransaction()
					syslog.syslog("transaction complete")
				else:
					syslog.syslog("no transaction tasks to complete")

				yb.closeRpmDB()
				yb.close()

			except Exception as ex:
				syslog.syslog("Error during yum transaction: " + str(type(ex)) + " " + str(ex))
				traceback.print_exc()
				yb.closeRpmDB()
				yb.close()

		# close sqlite3 before we quit
		conn.close()

	def addPackageTask(self,task):
		start = False
		if self.pkgProcess is None:
			start = True
		else:
			if not self.pkgProcess.is_alive():
				start = True
		
		if start:
			self.startPackageTask(task)
		else:
			syslog.syslog("added package task to queue")
			self.pkgTaskQueue.append(task)

	def startPackageTask(self,task):
		self.pkgTaskCurrent = task
		syslog.syslog("starting package process")
		self.pkgProcess = Process(target=self.pkgProcessTask, args=(task,))
		self.pkgProcess.start()
		
	## RPC METHODS #############################################################

	@Pyro4.expose
	def ping(self):
		return True

	## send a list of package IDs, where the ID corresponds to the ID in the
	## pkgdb sqlite database. in this way the web interface can ask what the 
	## status of a particular package is (e.g. if its being installed)
	@Pyro4.expose
	def pkgEntryInstall(self,pid):
		self.addPackageTask({'action': 'install', 'id': pid})

	@Pyro4.expose
	def pkgEntryRemove(self,pid):
		self.addPackageTask({'action': 'remove', 'id': pid})

	@Pyro4.expose
	def pkgEntryStatus(self,check_id):

		# Get the list of entries queued
		lst = self.pkgTaskQueue
		# add on the current task if the process is alive
		if not self.pkgProcess is None:
			if self.pkgProcess.is_alive():
				if self.pkgTaskCurrent is not None:
					lst = [self.pkgTaskCurrent] + lst
				

		# Loop over the list
		for task in lst:
			if int(task['id']) == int(check_id):
				if task['action'] == 'install':
					return 1 # this entry is being installed onto the system
				elif task['action'] == 'remove':
					return 2 # this entry is being removed from the system

		return 0 # entry was not in queue

	@Pyro4.expose
	def groupAddUser(self,group,username):
		if group not in self.allowed_groups:
			raise ValueError("That group is invalid")

		## validate the user
		try:
			pwd.getpwnam(username)
		except KeyError as ex:
			raise ValueError("That username is invalid")

		(code,output) = self.sysexec(["/usr/bin/gpasswd","-a",username,group])

		if code != 0:
			raise Exception("Could not add user to group: " + output)

	@Pyro4.expose
	def groupRemoveUser(self,group,username):
		if group not in self.allowed_groups:
			raise ValueError("That group is invalid")

		## validate the user
		try:
			pwd.getpwnam(username)
		except KeyError as ex:
			raise ValueError("That username is invalid")

		(code,output) = self.sysexec(["/usr/bin/gpasswd","-d",username,group])

		if code != 0:
			raise Exception("Could not remove user from group: " + output)

