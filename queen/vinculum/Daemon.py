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
from multiprocessing import Process, Queue
import traceback

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

	## PRIVATE METHODS #########################################################

	def __init__(self, pyro):
		syslog.openlog("vinculum", syslog.LOG_PID)

		## rename the process title
		setproctitle("vinculum-master")

		## Store the copy of the pyro daemon object
		self.pyro = pyro

		## Set up signal handlers
		signal.signal(signal.SIGTERM, self._signal_handler_master)
		signal.signal(signal.SIGINT, self._signal_handler_master)

		## Set up the queue of tasks for packages to install/remove
		self.pkgTaskQueue = Queue()

		## Start the process for performing package installs
		pkgProcess = Process(target=self._pkgProcess, args=(self.pkgTaskQueue,))
		pkgProcess.start()

		syslog.syslog('vinculum-master started')

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

		syslog.syslog('child process caught ' + str(sig) + "; exiting")
		sys.exit(0)

	## This is called on each pyro loop timeout/run to make sure defunct processes
	## (finished tasks waiting for us to reap them) are reaped
	def _onloop(self):
		multiprocessing.active_children()
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

	def _pkgProcess(self,q):
		setproctitle("vinculum-pkg")
		syslog.openlog("vinculum-pkg", syslog.LOG_PID)
		signal.signal(signal.SIGTERM, self._signal_handler_child)
		signal.signal(signal.SIGINT, self._signal_handler_child)
		syslog.syslog('vinculum-pkg started')
	
		while True:
			task = q.get(block=True)
			syslog.syslog("package task obtained")

			if task['task'] == 'pkgInstall' or task['task'] == "pkgRemove":
				pkg_names = task['data']

				try:
					yb=yum.YumBase()
					yb.conf.cache = 0

					transaction = False
					for pkg in pkg_names:

						## support the format name.arch
						arch=None
						if pkg.endswith(".i686"):
							pkg = pkg[:-5]
							arch = "i686"
						elif pkg.endswith(".x86_64"):
							pkg = pkg[:-7]
							arch = "x86_64"
						elif pkg.endswith(".noarch"):
							pkg = pkg[:-7]
							arch = "noarch"

						if task['task'] == 'pkgInstall':
							res = yb.install(name=pkg,arch=arch,silence_warnings=True)
						elif task['task'] == 'pkgRemove':
							res = yb.remove(name=pkg,arch=arch,silence_warnings=True)

						if len(res) > 0:
							transaction = True
						else:
							if task['task'] == 'pkgInstall':
								syslog.syslog("Could not install " + pkg)
							elif task['task'] == 'pkgRemove':
								syslog.syslog("Could not remove " + pkg)

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
					syslog.syslog("Error during package install: " + str(type(ex)) + " " + str(ex))			
					traceback.print_exc()
					yb.closeRpmDB()
					yb.close()
		
	## RPC METHODS #############################################################

	## groupAddUser
	## groupRemoveUser
	## 
	## backupNow

	@Pyro4.expose
	def ping(self):
		return True

	@Pyro4.expose
	def pkgInstall(self,pkg_names):
		self.pkgTaskQueue.put({'task': 'pkgInstall', 'data': pkg_names})
		syslog.syslog("added package install task to queue")

	@Pyro4.expose
	def pkgRemove(self,pkg_names):
		self.pkgTaskQueue.put({'task': 'pkgRemove', 'data': pkg_names})
		syslog.syslog("added package remove task to queue")

	@Pyro4.expose
	def pkgGroupInstall(self,grp_names):
		self.pkgTaskQueue.put({'task': 'pkgGroupInstall', 'data': grp_names})

	def pkgGroupRemove(self,grp_names):
		self.pkgTaskQueue.put({'task': 'pkgGroupRemove', 'data': grp_names})

	@Pyro4.expose
	def request_backup(self,name):
		syslog.syslog('started backup task for ' + system['name'] + ' with task id ' + str(task_id) + ' and worker pid ' + str(task.pid))
		return task_id
