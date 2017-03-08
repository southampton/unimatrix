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
import re
import dmidecode

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
	backupProcess  = None

	############################################################################
	## PRIVATE METHODS #########################################################
	############################################################################

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

	############################################################################

	def _signal_handler_master(self, sig, frame):
		if sig == signal.SIGTERM: 
			sig = "SIGTERM"
		elif sig == signal.SIGINT:
			sig = "SIGINT"

		syslog.syslog('master process caught ' + str(sig) + "; exiting")
		Pyro4.core.Daemon.shutdown(self.pyro)
		multiprocessing.active_children()
		sys.exit(0)

	############################################################################

	def _signal_handler_pkg(self, sig, frame):
		if sig == signal.SIGTERM: 
			sig = "SIGTERM"
		elif sig == signal.SIGINT:
			sig = "SIGINT"

		syslog.syslog('pkg worker process caught ' + str(sig) + "; exiting")
		sys.exit(0)

	def _signal_handler_backup(self, sig, frame):
		if sig == signal.SIGTERM: 
			sig = "SIGTERM"
		elif sig == signal.SIGINT:
			sig = "SIGINT"

		syslog.syslog('backup worker process caught ' + str(sig) + "; exiting")
		sys.exit(0)

	############################################################################

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

	############################################################################

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

	############################################################################

	def pkgProcessTask(self,task):
		setproctitle("deskctld-pkg")
		syslog.openlog("deskctld-pkg", syslog.LOG_PID)
		signal.signal(signal.SIGTERM, self._signal_handler_pkg)
		signal.signal(signal.SIGINT, self._signal_handler_pkg)
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

				## Now we need to get the individual packages or groups
				## which make up this 'entry'.
				cursor.execute("SELECT * FROM `items` WHERE `entry` = ?",(task['id'],))
				items = cursor.fetchall()

				transaction = False
				for item in items:
					# start of loop over each item

					# Check if we've been asked to install/remove a package group
					if item['name'].startswith("@"):
						group = True
						envgroup = False
						item_name = item['name'][1:]
						item_type = "group"
					# Check if we've been asked to install/remove an environment group
					elif item['name'].startswith("#"):
						group = True
						envgroup = True
						item_name = item['name'][1:]
						item_type = "group"
					# We must have been asked to process a normal package then
					else:
						group = False
						envgroup = False
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
								if envgroup:
									res = yb.selectEnvironment(evgrpid=item_name)
								else:									
									res = yb.selectGroup(grpid=item_name)
							except Exception as ex:
								syslog.syslog("Could not install group " + item_name + ": " + str(ex))
								continue

						elif task['action'] == 'remove':
							try:
								if envgroup:
									res = yb.environmentRemove(evgrpid=item_name)
								else:
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

		#
		syslog.syslog("exiting")

	############################################################################

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

	############################################################################

	def startPackageTask(self,task):
		self.pkgTaskCurrent = task
		syslog.syslog("starting package process")
		self.pkgProcess = Process(target=self.pkgProcessTask, args=(task,))
		self.pkgProcess.start()

	############################################################################		
	## RPC METHODS #############################################################
	############################################################################

	@Pyro4.expose
	def ping(self):
		return True

	############################################################################

	## send a list of package IDs, where the ID corresponds to the ID in the
	## pkgdb sqlite database. in this way the web interface can ask what the 
	## status of a particular package is (e.g. if its being installed)
	@Pyro4.expose
	def pkgEntryInstall(self,pid):
		self.addPackageTask({'action': 'install', 'id': pid})

	############################################################################

	@Pyro4.expose
	def pkgEntryRemove(self,pid):
		self.addPackageTask({'action': 'remove', 'id': pid})

	############################################################################

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

	############################################################################

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

	############################################################################

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

	############################################################################

	@Pyro4.expose
	def getHardwareInformation(self):
		return {
			'cpus'           : self.get_cpu_info(), 
			'physical_memory': self.get_phys_mem_info(), 
			'os_memory'      : self.get_mem_info(), 
			'filesystems'    : self.get_disk_info(), 
			'disks'          : self.get_phys_disk_info(), 
			'graphics'       : self.get_graphics_cards(), 
			'system'         : self.get_system_details()
		}

	############################################################################

	def get_graphics_cards(self):
		# Regular expression for graphics cards
		re_vga = re.compile(r'^[0-9a-f]+:[0-9a-f]+\.[0-9a-f]+\s+VGA\s+compatible\s+controller:\s+(.*)')

		# Get the information from df (it's just easier)
		(code,output) = self.sysexec(['/usr/sbin/lspci'])
		
		cards = []

		# Iterate over the output
		for line in output.splitlines():
			vga_match = re_vga.search(line)
			if vga_match is not None:
				cards.append(vga_match.group(1))

		return {'cards': cards}

	############################################################################

	def get_phys_disk_info(self):
		# Setup
		disks = {}

		# Search through every device in /sys/block
		for block_dev in os.listdir('/sys/block'):
			# Only investigate hd* or sd* devices (so IDE disks and SCSI disks)
			if (block_dev[0] == 'h' or block_dev[0] == 's') and block_dev[1] == 'd':

				# Read their size (in 512-byte blocks)
				f = open('/sys/block/' + block_dev + '/size')
				size = f.readline()
				f.close()

				# Read the model name of the disk
				try:
					f = open('/sys/block/' + block_dev + '/device/model')
					model = f.readline()
					f.close() 
				except Exception as ex:
					model = "Unknown disk"

				# Read the vendor name of the disk
				try:
					f = open('/sys/block/' + block_dev + '/device/vendor')
					vendor = f.readline()
					f.close() 
				except Exception as ex:
					vendor = ""

				disks[block_dev] = {'size': int(size) * 512, 'model': model, 'vendor': vendor, 'dev': block_dev}

		return disks

	############################################################################

	def get_disk_info(self):
		# Regular expression for this
		re_disk = re.compile(r'^\s*([0-9]+)\s+([0-9]+)\s+([0-9]+)\s+([0-9]+)\%\s+(.*)')

		# Get the information from df (it's just easier)
		(code,output) = self.sysexec(['/bin/df', '--output=size,used,avail,pcent,target', '-x', 'tmpfs', '-x', 'devtmpfs', '-x', 'shm'])

		disks = {}

		# Iterate over the output
		for line in output.splitlines():
			disk_match = re_disk.search(line)

			if disk_match is not None:
				# exclude /boot we dont need it
				if disk_match.group(5) != '/boot':

					disks[disk_match.group(5)] = {'size': int(disk_match.group(1)) * 1024, 'used': int(disk_match.group(2)) * 1024, 'available': int(disk_match.group(3)) * 1024, 'pc': int(disk_match.group(4)) }

		return disks

	############################################################################

	def get_phys_mem_info(self):
		total = 0
		for mem in dmidecode.memory().values():
			if 'Form Factor' in mem['data']:
				if mem['data']['Form Factor'] in ['DIMM','SODIMM']:
					if 'Size' in mem['data'] and mem['data']['Size'] is not None:
						parts = mem['data']['Size'].split(' ')
						number = parts[0]
						unit = parts[1]

						# Store size in bytes
						if unit == 'KB' or unit == 'KiB':
							size = int(number) * 1024
						elif unit == 'MB' or unit == 'MiB':
							size = int(number) * 1048576
						elif unit == 'GB' or unit == 'GiB':
							size = int(number) * 1073741824
						elif unit == 'TB' or unit == 'TiB':
							size = int(number) * 1099511627776
						else:
							size = int(number)

						total = total + size

		return {'installed_ram': total}

	############################################################################

	def get_mem_info(self):
		# Regular expressions for parsing meminfo
		re_total     = re.compile(r'^MemTotal:\s+([0-9]+)\s+kB')
		re_free      = re.compile(r'^MemFree:\s+([0-9]+)\s+kB')
		re_available = re.compile(r'^MemAvailable:\s+([0-9]+)\s+kB')

		# Set up
		results = {}

		# Read the entire file
		meminfo = open('/proc/meminfo', 'r')
		for line in meminfo:
			# Match the line against our regexs
			total_match     = re_total.search(line)
			free_match      = re_free.search(line)
			available_match = re_available.search(line)

			if total_match is not None:
				results['total_usable'] = int(total_match.group(1)) * 1024
			elif free_match is not None:
				results['free'] = int(free_match.group(1)) * 1024
			elif available_match is not None:
				results['available'] = int(available_match.group(1)) * 1024

		return results

	############################################################################

	def get_cpu_info(self):
		# Regular expressions for parsing cpuinfo
		re_processor = re.compile(r'^processor\s*:\s+([0-9]+)')
		re_physical_id = re.compile(r'^physical\sid\s*:\s+([0-9]+)')
		re_cpu_cores = re.compile(r'^cpu\scores\s*:\s+([0-9]+)')
		re_model_name = re.compile(r'^model\sname\s*:\s+(.*)')
		re_cache_size = re.compile(r'^cache\ssize\s*:\s+(.*)')

		# Setup
		processor = None
		cpu = None
		cpu_cores = None
		model = None
		cache_size = None
		procs = {}

		# Read the entire cpuinfo file
		cpuinfo = open('/proc/cpuinfo', 'r')
		for line in cpuinfo:
			# Match the line against our regexs
			p_match     = re_processor.search(line)
			pid_match   = re_physical_id.search(line)
			cpu_match   = re_cpu_cores.search(line)
			model_match = re_model_name.search(line)
			cache_match = re_cache_size.search(line)

			if p_match is not None:
				# We're starting a new CPU, record the old one
				if cpu is not None and cpu not in procs:
					procs[cpu] = { 'model': model, 'cores': cpu_cores, 'cache': cache_size }
				
				#processor = int(p_match.group(1))
				cpu = None
				cpu_core = None
				model = None

			if pid_match is not None:
				cpu = int(pid_match.group(1))

			if cpu_match is not None:
				cpu_cores = int(cpu_match.group(1))

			if model_match is not None:
				model = model_match.group(1)

			if cache_match is not None:
				cache_size = cache_match.group(1)

		# Pick up the last CPU
		if cpu is not None and cpu not in procs:
			procs[cpu] = { 'model': model, 'cores': cpu_cores, 'cache': cache_size }

		return procs

	############################################################################

	def get_system_details(self):
		try:
			system_values = dmidecode.system().values()
		except Exception as ex:
			system_values = []

		vendor = None
		try:
			for entry in system_values:
				if 'data' in entry:
					if 'Manufacturer' in entry['data']:
						vendor = entry['data']['Manufacturer']
						break
		except Exception as ex:
			pass

		model = None
		try:
			for entry in system_values:
				if 'data' in entry:
					if 'Product Name' in entry['data']:
						model = entry['data']['Product Name']
						break
		except Exception as ex:
			pass

		return {'vendor': vendor, 'model': model}

	############################################################################

	@Pyro4.expose
	def backup_now(self):
		start = not self.is_backup_in_progress()
		
		if start:
			syslog.syslog("starting backup process")
			self.backupProcess = Process(target=self.backupProcessTask)
			self.backupProcess.start()

	@Pyro4.expose
	def is_backup_in_progress(self):
		if self.backupProcess is not None:
			if self.backupProcess.is_alive():
				return True
		
		return False

	############################################################################

	def backupProcessTask(self):
		setproctitle("deskctld-backuo")
		syslog.openlog("deskctld-bacup", syslog.LOG_PID)
		signal.signal(signal.SIGTERM, self._signal_handler_backup)
		signal.signal(signal.SIGINT, self._signal_handler_backup)
		syslog.syslog('backup worker process started')

		(code, output) = self.sysexec(["/sbin/drone","backup","now"])

		if code == 0:
			syslog.syslog('backup successful')
		else:
			syslog.syslog('backup non-zero exit, run drone backup status')
