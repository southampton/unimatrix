#!/usr/bin/python

from zero import app
from flask import g, flash, request, abort
import MySQLdb as mysql
import traceback
import bcrypt
from datetime import datetime, timedelta

################################################################################

def get_system_by_name(name):

	curd = g.db.cursor(mysql.cursors.DictCursor)
	curd.execute("""SELECT 
       `systems`.`id` AS `id`, 
       `systems`.`name` AS `name`, 
       `systems`.`create_date` AS `create_date`,
       `systems`.`register_date` AS `register_date`,
       `systems`.`last_seen_date` AS `last_seen_date`,
       `systems`.`last_seen_addr` AS `last_seen_addr`,
       `systems_data`.`facts` AS `facts`,
       `systems_data`.`metadata` AS `metadata`,
       `systems_data`.`backup_status` AS `backup_status`,
       `systems_data`.`update_status` AS `update_status`,
       `systems_data`.`puppet_status` AS `puppet_status`
       FROM `systems` 
       LEFT JOIN `systems_data` 
       ON `systems`.`id` = `systems_data`.`sid` WHERE `systems`.`name` = %s""",(name,))

	system = curd.fetchone()

	## json load 
	try:
		system['facts'] = json.loads(system['facts'])
	except Exception as ex:
		system['facts'] = None

	try:
		system['metadata'] = json.loads(system['metadata'])
	except Exception as ex:
		system['metadata'] = None

	try:
		system['backup_status'] = json.loads(system['backup_status'])
	except Exception as ex:
		system['backup_status'] = None

	try:
		system['update_status'] = json.loads(system['update_status'])
	except Exception as ex:
		system['update_status'] = None

	try:
		system['puppet_status'] = json.loads(system['puppet_status'])
	except Exception as ex:
		system['puppet_status'] = None

	time_three_days_ago     = datetime.now() - timedelta(days=3)

	## ostatus
	## 0 - OK
	## 1 - backup failed
	## 2 - partial
	## 3 - too old (backup was too long ago)
	## 4 - no backups (error)

	# determine server backup status ('sstatus')
	## 0 - success
	## 1 - error
	## 2 - partial
	## 3 - too old
	## 4 - no backups

	curd.execute("""SELECT * FROM `tasks` WHERE `name` = 'backup' AND `sid` = %s ORDER BY `id` DESC LIMIT 0,1""",(system['id'],))
	last_backup = curd.fetchone()

	if last_backup == None:
		system['backup_sstatus'] = 4
		system['backup_ostatus'] = 4
		system['backup_swhen'] = None
	else:
		system['backup_swhen'] = last_backup['end']

		if int(last_backup['status']) != 0:
			system['backup_sstatus'] = 0
			system['backup_ostatus'] = 0
		if int(last_backup['status']) == 1: # 1 in the 'tasks' table actually means partial - for reasons, I'm sure.
			system['backup_sstatus'] = 2
			system['backup_ostatus'] = 2
		else: 
			system['backup_sstatus'] = 1
			system['backup_ostatus'] = 1
 
		time_last_server_backup = datetime.utcfromtimestamp(int(last_backup['end']))
		if time_last_server_backup < time_three_days_ago:
			system['backup_sstatus'] = 3
			system['backup_ostatus'] = 3

	## determine client backup status ('cstatus')
	if system['backup_status'] is not None:

		if 'code' in system['backup_status']:
			if int(system['backup_status']) == 0:
				system['backup_cstatus'] = 0
				system['backup_ostatus'] = 0
			elif int(system['backup_status']) == 1:
				system['backup_cstatus'] = 2
				system['backup_ostatus'] = 2
			else:
				system['backup_cstatus'] = 1
				system['backup_ostatus'] = 1

		if 'when' in system['backup_status']: 
			## time, minus 3 days ago (before that, and we consider the backup status
			## to be 'bad' because there hasnt been a backup in a long time)
			time_last_client_backup = datetime.utcfromtimestamp(int(system['backup_status']['when']))
			if time_last_client_backup < time_three_days_ago:
				system['backup_cstatus'] = 3
	else:
		system['backup_cstatus'] = 4
		system['backup_ostatus'] = 4

	## determine overall system status

	## determine power status


	return system

################################################################################

def system_api_auth():
	hostname = request.form['hostname']
	api_key  = request.form['api_key']

	app.logger.debug("system_api_auth: request to auth " + hostname)

	# Locate the hostname in the database
	curd = g.db.cursor(mysql.cursors.DictCursor)
	curd.execute("SELECT * FROM `systems` WHERE `name` = %s",(request.form['hostname'].lower(),))
	system = curd.fetchone()

	## that hostname is not valid, no such system!
	if system == None:
		abort(404)

	if isinstance(api_key, unicode):
		api_key = api_key.encode('utf8')
	if isinstance(system['api_key'], unicode):
		system['api_key'] = system['api_key'].encode('utf8')

	## check the API key - its bcrypt encrypted in the DB
	if bcrypt.checkpw(api_key, system['api_key']):
		return system
	else:
		abort(403)

################################################################################

def system_api_checkin(system,addr=None):
	if addr is None:
		if request:
			if request.remote_addr:
				addr = request.remote_addr
			else:
				addr = "Unknown"
		else:
			addr = "Unknown"

	curd = g.db.cursor(mysql.cursors.DictCursor)
	curd.execute('UPDATE `systems` SET `last_seen_date` = NOW(), `last_seen_addr` = %s WHERE `id` = %s',(addr,system['id'],))
	g.db.commit()

################################################################################

def get_system_backup_port(system_id):
	curd = g.db.cursor(mysql.cursors.DictCursor)
	curd.execute('SELECT `port` FROM `systems_backup_ports` WHERE `sid` = %s', (system_id,))
	result = curd.fetchone()
	if result:
		if 'port' in result:
			return result['port']

	return None

################################################################################

def register_system_backup_port(system_id):
	## outline of how this function works:
	# gets a lock on the table 'backup_ports'
	# checks to see if there are any null entries in the table, indicating a free'd port we should use
	# if not, add a new row instead
	# unlock table

	## Get the dict cursor
	curd = g.db.cursor(mysql.cursors.DictCursor)

	## 1. Lock the table
	curd.execute('LOCK TABLE `systems_backup_ports` WRITE;')

	## Everything now must be protected against exceptions becuase we *must*
	## try to unlock the table again even if something goes wrong, otherwise
	## the table might remain locked and unusable

	result = None
	try:
		## 2. Get the first entry (if any) in the table which is null
		curd.execute('SELECT MIN(`port`) AS `port` FROM `systems_backup_ports` WHERE `sid` IS NULL')
		result = curd.fetchone()
	except Exception as ex:
		app.logger.error("register_system_port: Error whilst checking for reusable ports - " + str(type(ex)) + " - " + str(ex))
		app.logger.error(traceback.format_exc())
		curd.execute("UNLOCK TABLES")
		raise Exception("Unable to check for reusable ports")

	
	if result is not None:
		if 'port' in result:
			if result['port'] is not None:
				## 3. Reuse the port we just found
				try:
					curd.execute("UPDATE `systems_backup_ports` SET `sid` = %s WHERE `port` = %s",(system_id,result['port'],))
					app.logger.info("register_system_port: allocated port " + str(result['port']) + " to system ID " + str(system_id))
					curd.execute("UNLOCK TABLES")
					return int(result['port'])
				except Exception as ex:
					app.logger.error("register_system_port: Error whilst allocating a reused port  - " + str(type(ex)) + " - " + str(ex))
					app.logger.error(traceback.format_exc())
					curd.execute("UNLOCK TABLES")
					raise Exception("Unable to check for reusable ports")

	app.logger.info("register_system_port: No ports could be recycled")

	## Determine the next port number to use
	try:
		curd.execute('SELECT MAX(`port`) AS `port` FROM `systems_backup_ports`')
		result = curd.fetchone()
	except Exception as ex:
		app.logger.error("register_system_port: Error whilst checking for the next port to use - " + str(type(ex)) + " - " + str(ex))
		app.logger.error(traceback.format_exc())
		curd.execute("UNLOCK TABLES")
		raise Exception("Unable to determine a backup port")

	new_port = None
	if result is not None:
		if 'port' in result:
			if result['port'] is not None:
				new_port = int(result['port']) + 1

	if new_port == None:
		new_port = app.config['BACKUP_PORT_MIN']

	if new_port > app.config['BACKUP_PORT_MAX']:
		app.logger.error("register_system_port: Cannot allocate a new backup port, no ports free (BACKUP_PORT_MAX reached)")
		app.logger.error(traceback.format_exc())
		curd.execute("UNLOCK TABLES")
		raise Exception("Unable to determine a backup port - no free ports")

	try:
		curd.execute("INSERT INTO `systems_backup_ports` (`port`, `sid`) VALUES (%s, %s)", (new_port, system_id,))
		curd.execute("UNLOCK TABLES")
		app.logger.info("register_system_port: allocated port " + str(new_port) + " to system ID " + str(system_id))
		return int(new_port)
	except Exception as ex:
		app.logger.error("register_system_port: Could not insert new port record - " + str(type(ex)) + " - " + str(ex))
		app.logger.error(traceback.format_exc())
		curd.execute("UNLOCK TABLES")
		raise Exception("Unable to determine a backup port")
