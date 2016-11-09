#!/usr/bin/python

from zero import app
from flask import g, flash
import MySQLdb as mysql

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
		curd.execute("UNLOCK TABLES")
		raise Exception("Unable to check for reusable ports")

	
	if result is not None:
		if 'port' in result:
			## 3. Reuse that port
			try:
				curd.execute("UPDATE `systems_backup_ports` SET `sid` = %s WHERE `port` = %s",(system_id,result['port'],))
				app.logger.info("register_system_port: allocated port " + result['port'] + " to system ID " + system_id)
				curd.execute("UNLOCK TABLES")
				return int(result['port'])
			except Exception as ex:
				app.logger.error("register_system_port: Error whilst allocating a reused port  - " + str(type(ex)) + " - " + str(ex))
				curd.execute("UNLOCK TABLES")
				raise Exception("Unable to check for reusable ports")

	app.logger.info("register_system_port: No ports could be recycled")
	curd.execute("INSERT INTO `systems_backup_ports` (`sid`) VALUES (%s)", (system_id,result['port'],))
	port = curd.lastrowid
	curd.execute("UNLOCK TABLES")
	app.logger.info("register_system_port: allocated port " + port + " to system ID " + system_id)
	return int(port)
