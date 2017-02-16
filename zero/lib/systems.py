#!/usr/bin/python

from zero import app
from flask import g, flash, request, abort
import MySQLdb as mysql
import traceback
import bcrypt

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

def system_api_checkin(system):
	curd = g.db.cursor(mysql.cursors.DictCursor)
	curd.execute('UPDATE `systems` SET `last_seen_date` = NOW() WHERE `id` = %s',(system['id'],))
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
