#!/usr/bin/python

import Pyro4
import syslog
import signal
import os
import imp
import MySQLdb as mysql
import sys
import requests
import json
import time
from setproctitle import setproctitle #pip install setproctitle

class BackupTask(object):

	def __init__(self, task_id, system, config):
		self.config        = config
		self.system        = system
		self.task_id       = task_id

	def _signal_handler(self, signal, frame):
		syslog.syslog('task id ' + str(self.task_id) + ' caught exit signal')
		self._end_task(success=False)
		syslog.syslog('task id ' + str(self.task_id) + ' marked as finished')
		sys.exit(0)

	def sysexec(self,command,shell=False):
		try:
			proc = subprocess.Popen(command,stdout=subprocess.PIPE, stderr=subprocess.STDOUT,shell=shell)
			(stdoutdata, stderrdata) = proc.communicate()
			if stdoutdata is None:
				stdoutdata = ""
			if stderrdata is None:
				stderrdata = ""

			return (proc.returncode,str(stdoutdata),str(stderrdata))
		except Exception as ex:
			return (1,"",str(type(ex)) + " " + str(ex))

	def run(self):

		syslog.syslog('backup-task ' + str(self.task_id) + " starting")

		## Set up signal handlers to mark the task as error'ed
		signal.signal(signal.SIGTERM, self._signal_handler)
		signal.signal(signal.SIGINT, self._signal_handler)

		self.db   = self.db_connect()
		self.curd = self.db.cursor(mysql.cursors.DictCursor)

		## Set the process name
		setproctitle("plexus-backup ID " + str(self.task_id) + " for " + self.system['name'])

		try:
			sysdir = os.path.join(self.config['BACKUP_ROOT_DIR'],self.system['name'])
			if not os.path.exists(sysdir):
				os.mkdir(sysdir)

			sysbackupsdir = os.path.join(sysdir,'backups')
			if not os.path.exists(sysbackupsdir):
				os.mkdir(sysbackupsdir)

			self.curd.execute("SELECT * FROM `systems_backup_ports` WHERE `sid` = %s",(self.system['id'],))
			result = self.curd.fetchone()

			if result is None:
				raise Exception("No backup port assigned to the chosen system!")

			backup_port = result['port']

			(code, stdout, stderr) = self.sysexec("""/usr/bin/rsync -av --delete rsync://backup@localhost:%s/home/ %s/home/""" % (backup_port,sysbackupsdir,),shell=True)

			if code == 0:
				syslog.syslog('backup success')
			else:
				syslog.syslog('backup failed :(')

			## TODO save backup log
			## 5. update status

			self._end_task()
		except Exception as ex:
			syslog.syslog('backup task ' + str(self.task_id) + " failed: " + str(type(ex)) + " " + str(ex))
			self._end_task(success=False)

	def db_connect(self):
		return mysql.connect(self.config['MYSQL_HOST'], self.config['MYSQL_USER'], self.config['MYSQL_PASS'], self.config['MYSQL_NAME'], charset='utf8')

	def _end_task(self, success=True):
		if success:
			status = 1
		else:
			status = 2

		self.curd.execute("UPDATE `tasks` SET `status` = %s, `end` = NOW() WHERE `id` = %s", (status, self.task_id))
		self.db.commit()
