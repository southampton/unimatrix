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
import subprocess
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

	def run(self):

		syslog.syslog('backup-task ' + str(self.task_id) + " starting for system " + self.system['name'])

		try:
			## Set up signal handlers to mark the task as error'ed
			signal.signal(signal.SIGTERM, self._signal_handler)
			signal.signal(signal.SIGINT, self._signal_handler)

			self.db   = self.db_connect()
			self.curd = self.db.cursor(mysql.cursors.DictCursor)

			## Set the process name
			setproctitle("plexus-backup ID " + str(self.task_id) + " for " + self.system['name'])
		except Exception as ex:
			syslog.syslog('backup task ' + str(self.task_id) + " could not start due to an internal error: " + str(type(ex)) + " " + str(ex))

		try:
			sysdir = os.path.join(self.config['BACKUP_ROOT_DIR'],self.system['name'])
			if not os.path.exists(sysdir):
				os.mkdir(sysdir)

			sysbackupsdir = os.path.join(sysdir,'backups')
			if not os.path.exists(sysbackupsdir):
				os.mkdir(sysbackupsdir)

			logdir = os.path.join(sysdir,'logs')
			if not os.path.exists(logdir):
				os.mkdir(logdir)

			self.curd.execute("SELECT * FROM `systems_backup_ports` WHERE `sid` = %s",(self.system['id'],))
			result = self.curd.fetchone()

			if result is None:
				raise Exception("No backup port assigned to the chosen system!")

			backup_port = result['port']

			procenv = {'RSYNC_PASSWORD': self.system['backup_key']}
			(code, output) = self.sysexec("""/usr/bin/rsync -a --delete rsync://backup@localhost:%s/home/ %s""" % (backup_port,os.path.join(sysbackupsdir,"home"),),shell=True,env=procenv)

			## we store the backup log in the database, but lets also store it on disk
			## in case we want to see it later
			try:
				with open(os.path.join(logdir,"rsync.log"),"w") as fp:
					fp.write(output)
			except Exception as ex:
				syslog.syslog('WARN: Could not write to ' + os.path.join(logdir,"rsync.log") + ": " + str(ex))

			if code == 0:
				status = 0
				result = "backup OK"
			elif code == 23 or code == 24:
				status = 1
				result = "partial failure"
			else:
				status = 2
				result = "backup failure"

			syslog.syslog('backup-task ' + str(self.task_id) + " finished for " + self.system['name'] + " result: " + result)
			self._end_task(status=status,result=output)
		except Exception as ex:
			syslog.syslog('backup task ' + str(self.task_id) + " failed due to an internal error: " + str(type(ex)) + " " + str(ex))
			self._end_task(status=3,result="Internal error: " + str(type(ex)) + " " + str(ex))

	def db_connect(self):
		return mysql.connect(self.config['MYSQL_HOST'], self.config['MYSQL_USER'], self.config['MYSQL_PASS'], self.config['MYSQL_NAME'], charset='utf8')

	def _end_task(self, status, result="Unknown"):
		# 0 = success
		# 1 = partial transfer
		# 2 = failed, rsync command failed
		# 3 = failed, python exception
		try:
			self.curd.execute("UPDATE `tasks` SET `status` = %s, `end` = NOW(), `result` = %s WHERE `id` = %s", (status, result, self.task_id))
			self.curd.execute("UPDATE `systems` SET `last_seen_date` = NOW() WHERE `id` = %s", (self.system['id'],))
			self.db.commit()
		except Exception as ex:
			syslog.syslog('backup task ' + str(self.task_id) + " could not mark itself finished: " + str(type(ex)) + " " + str(ex))
