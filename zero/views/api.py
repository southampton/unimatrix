#!/usr/bin/python

from zero import app
from zero.lib.user import is_logged_in, authenticate, is_user_in_group
from zero.lib.systems import register_system_backup_port, get_system_backup_port
from flask import Flask, request, session, redirect, url_for, flash, g, abort, make_response, render_template, jsonify
import MySQLdb as mysql
import re

####
from paramiko import RSAKey
####
import StringIO
####

################################################################################

@app.route('/api/v1/register', methods=['POST'])
@app.disable_csrf_check
def api_register():
	"""Simple REST API endpoint to allow workstations to register"""

	app.logger.debug("call: api_register()")

	## We return 200 OK whatever errors we encounter
	## we return JSON, and if there is an error
	## the JSON has an 'error' variable set with the problem

	username = request.form['username']

	app.logger.debug("api_register: username sent was " + username)

	## Check username + password in LDAP
	result = authenticate(username, request.form['password'])

	if not result:
		app.logger.debug("api_register: request failed, authentication failure for " + username)
		return jsonify({'error': True, 'reason': "Authentication failure, incorrect username and/or password"})
	else:
		app.logger.debug("api_register: authentication success for " + username)

	## Only allow iSolutions staff to register systems
	if not is_user_in_group(username,"jfStaff"):
		app.logger.debug("api_register: request failed, the user " + username + " is not in jfStaff")
		return jsonify({'error': True, 'reason': "Permission denied, you must be a member of iSolutions staff"})

	## Validate hostname
	hostname = request.form['hostname']

	if not re.match(r"^(uos|iss|lnx)\-[0-9]{2,8}$",hostname):
		app.logger.debug("api_register: request failed, the hostname " + hostname + " is invalid")
		return jsonify({'error': True, 'reason': "The hostname is invalid, it must be the uos-number of the system"})

	try:
		## Generate an SSH RSA private key
		private_key = RSAKey.generate(bits=2048)
		fakefile    = StringIO.StringIO()
		private_key.write_private_key(fakefile)
		private_key_str = fakefile.getvalue()

		## Reseek to 0 in our fake StringIO file
		fakefile.seek(0)

		## Generate an SSH RSA public key
		public_key = RSAKey.from_private_key(fakefile)

		## Turn it into a more usual output format
		public_key_str = public_key.get_name() + " " + public_key.get_base64()

	except Exception as ex:
		app.logger.debug("api_register: failed to generate ssh public/private keypair: " + str(type(ex)) + " - " + str(ex))
		return jsonify({'error': True, 'reason': "The server was unable to generate a ssh keypair"})		

	## Generate a secret key (64 bytes = 128 characters)
	backup_key = app.token(64)

	## Check if the system already exists in the database
	curd = g.db.cursor(mysql.cursors.DictCursor)
	
	curd.execute('SELECT `id` FROM `systems` WHERE `name` = %s', (hostname,))
	sysid = curd.fetchone()
	if sysid is None:
		## System does not exist, create a new one
		try:
			curd.execute("INSERT INTO `systems` (`name`, `create_date`, `register_date`, `last_seen_date`, `ssh_public_key`, `backup_key`) VALUES (%s, NOW(), NOW(), NOW(), %s, %s)", (hostname, public_key_str, backup_key,))
			g.db.commit()
		except Exception as ex:
			app.logger.debug("api_register: failed to create system record " + str(type(ex)) + " - " + str(ex))
			return jsonify({'error': True, 'reason': "The server was unable to save the system record"})

		## Register a port number
		try:
			backup_port = register_system_backup_port(curd.lastrowid)
		except Exception as ex:
			app.logger.error("api_register: failed to register system backup port " + str(type(ex)) + " - " + str(ex))
			return jsonify({'error': True, 'reason': "The server was unable to assign a backup port number"})

	else:
		try:
			curd.execute("UPDATE `systems` SET `register_date` = NOW(), `last_seen_date` = NOW(), `ssh_public_key` = %s, `backup_key` = %s WHERE `id` = %s", (public_key_str, backup_key, sysid['id'],))
			g.db.commit()
		except Exception as ex:
			app.logger.debug("api_register: failed to update system record during re-registration: " + str(type(ex)) + " - " + str(ex))
			return jsonify({'error': True, 'reason': "The server was unable to save the system record"})

		## Get the existing port number
		backup_port = get_system_backup_port(sysid['id'])

		if backup_port is None:
			try:
				backup_port = register_system_backup_port(sysid['id'])
			except Exception as ex:
				app.logger.debug("api_register: failed to register system backup port " + str(type(ex)) + " - " + str(ex))
				return jsonify({'error': True, 'reason': "The server was unable to assign a backup port number"})
		else:
			app.logger.info("api_register: Reusing existing allocated backup port number for " + hostname)

	app.logger.info("api_register: registration complete for " + hostname + " using account " + username)
	return jsonify({'private_key': private_key_str, 'public_key': public_key_str, 'backup_key': backup_key, 'backup_port': backup_port})
