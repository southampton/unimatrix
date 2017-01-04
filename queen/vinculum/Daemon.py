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

# we use multiplex, rather than threading, cos the GIL sucks.
Pyro4.config.SERVERTYPE = "multiplex"
Pyro4.config.SOCK_REUSE = True

################################################################################

def set_socket_permissions(socket_path):
	## set perms on the socket path
	try:
		## TODO change the GID (1000) to a proper group the web server runs as
		os.chown(socket_path,0,1000)
	except Exception as ex:
		sys.stderr.write("Could not chown socket: " + str(type(ex)) + " " + str(ex))
		sys.exit(1)

	try:
		os.chmod(socket_path,0770)
	except Exception as ex:
		sys.stderr.write("Could not chmod socket: " + str(type(ex)) + " " + str(ex))
		sys.exit(1)

################################################################################

class VinculumDaemon(object):

	pyro  = None

	## PRIVATE METHODS #########################################################

	def __init__(self, pyro):
		syslog.openlog("vinculum", syslog.LOG_PID)

		## rename the process title
		setproctitle("vinculum")

		## Store the copy of the pyro daemon object
		self.pyro = pyro

		## Set up signal handlers
		signal.signal(signal.SIGTERM, self._signal_handler_term)
		signal.signal(signal.SIGINT, self._signal_handler_int)

	def _signal_handler_term(self, signal, frame):
		self._signal_handler('SIGTERM')
	
	def _signal_handler_int(self, signal, frame):
		self._signal_handler('SIGINT')
	
	def _signal_handler(self, signal):
		syslog.syslog('caught ' + str(signal) + "; exiting")
		Pyro4.core.Daemon.shutdown(self.pyro)
		sys.exit(0)

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
		
	## RPC METHODS #############################################################

	## pkgInstall
	## pkgRemove
	## pkgGroupInstall
	## pkgGroupRemove
	## groupAddUser
	## groupRemoveUser
	## 
	## backupNow
	## policySync
	## policyApply
	## policyRun

	@Pyro4.expose
	def ping(self):
		return True

	@Pyro4.expose
	def pkgInstall(self,pkg_names):
		yb=yum.YumBase()
		yb.conf.cache = 0
		installedPkgs = yb.rpmdb.returnPackages()
		installedPkgNames=[x.name for x in installedPkgs]

		found = False
		for pkg in pkg_names:
			if pkg in installedPkgNames:
				raise Exception("Package '" + pkg + "' is already installed")

			searchlist=['name']
			arg=[pkg]
			matches = yb.searchGenerator(searchlist,arg)

			for (package, matched_value) in matches:
				if package.name == pkg:
					yb.install(package)
					found = True
	
		if found:
			yb.buildTransaction()
			yb.processTransaction()
		else:
			raise Exception("Could not find matching packages to install")

	@Pyro4.expose
	def request_backup(self,name):
		syslog.syslog('started backup task for ' + system['name'] + ' with task id ' + str(task_id) + ' and worker pid ' + str(task.pid))
		return task_id

