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
			## 1. make sure the parent directory exists
			## 2. get the backup port from the DB
			## 3. run rsync
			## 4. save backup log
			## 5. update status


			time.sleep(60)
			syslog.syslog('fake backup finished')
			self._end_task()
		except Exception as ex:
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
