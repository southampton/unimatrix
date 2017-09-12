#!/usr/bin/python

from zero import app
from zero.lib.user import is_logged_in, authenticate, is_user_in_group
from zero.lib.systems import register_system_backup_port, get_system_backup_port, system_api_auth, system_api_checkin
from zero.lib.errors import stderr
from flask import Flask, request, session, redirect, url_for, flash, g, abort, make_response, render_template, jsonify
import MySQLdb as mysql
import re
from paramiko import RSAKey
import StringIO
import bcrypt
import json

################################################################################

@app.route('/api/v1/register', methods=['POST'])
@app.register_api_function
def api_v1_register():
	"""REST API endpoint to allow workstations to register"""

	app.logger.debug("call: api_v1_register()")

	## We return 200 OK whatever errors we encounter
	## we return JSON, and if there is an error
	## the JSON has an 'error' variable set with the problem

	username = request.form['username']

	app.logger.debug("api_v1_register: username sent was " + username)

	## Check username + password in LDAP
	result = authenticate(username, request.form['password'])

	if not result:
		app.logger.debug("api_v1_register: request failed, authentication failure for " + username)
		return jsonify({'error': True, 'reason': "Authentication failure, incorrect username and/or password"})
	else:
		app.logger.debug("api_v1_register: authentication success for " + username)

	## Only allow iSolutions staff to register systems
	if not is_user_in_group(username,"jfStaff"):
		app.logger.debug("api_v1_register: request failed, the user " + username + " is not in jfStaff")
		return jsonify({'error': True, 'reason': "Permission denied, you must be a member of iSolutions staff"})

	## Validate hostname
	hostname = request.form['hostname']

	if not re.match(r"^(((uos|iss|lnx|UOS|ISS|LNX)\-[0-9]{2,8})|([A-Za-z][0-9]{2,8}))$",hostname):
		app.logger.debug("api_v1_register: request failed, the hostname " + hostname + " is invalid")
		return jsonify({'error': True, 'reason': "The hostname is invalid, it must be the uos-number of the system"})
	else:
		hostname = hostname.lower()

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
		app.logger.debug("api_v1_register: failed to generate ssh public/private keypair: " + str(type(ex)) + " - " + str(ex))
		return jsonify({'error': True, 'reason': "The server was unable to generate a ssh keypair"})		

	## Generate a secret key for backups (64 bytes = 128 characters)
	backup_key = app.token(64)

	## Generate a secret key for API calls (32 bytes = 64 characters - we
	## will bcrypt encrypt the key and bcrypt only supports passwords up to 72
	## characters long :(
	api_key = app.token(32)
	
	## bcrypt encrypt the api_key for storage in the database
	enc_api_key = bcrypt.hashpw(api_key, bcrypt.gensalt())

	## Check if the system already exists in the database
	curd = g.db.cursor(mysql.cursors.DictCursor)
	
	curd.execute('SELECT `id` FROM `systems` WHERE `name` = %s', (hostname,))
	sysid = curd.fetchone()
	if sysid is None:
		## System does not exist, create a new one
		try:
			curd.execute("INSERT INTO `systems` (`name`, `create_date`, `register_date`, `last_seen_date`, `last_seen_addr`, `ssh_public_key`, `backup_key`, `api_key`) VALUES (%s, NOW(), NOW(), NOW(), %s, %s, %s, %s)", (hostname, request.remote_addr, public_key_str, backup_key, enc_api_key,))
			g.db.commit()
		except Exception as ex:
			app.logger.debug("api_v1_register: failed to create system record " + str(type(ex)) + " - " + str(ex))
			return jsonify({'error': True, 'reason': "The server was unable to save the system record"})

		## Register a port number
		try:
			backup_port = register_system_backup_port(curd.lastrowid)
		except Exception as ex:
			app.logger.error("api_v1_register: failed to register system backup port " + str(type(ex)) + " - " + str(ex))
			return jsonify({'error': True, 'reason': "The server was unable to assign a backup port number"})

		sysid = {'id': curd.lastrowid}

	else:
		try:
			curd.execute("UPDATE `systems` SET `register_date` = NOW(), `last_seen_date` = NOW(), `ssh_public_key` = %s, `backup_key` = %s, `api_key` = %s WHERE `id` = %s", (public_key_str, backup_key, enc_api_key, sysid['id']))
			g.db.commit()
		except Exception as ex:
			app.logger.debug("api_v1_register: failed to update system record during re-registration: " + str(type(ex)) + " - " + str(ex))
			return jsonify({'error': True, 'reason': "The server was unable to save the system record"})

		## Get the existing port number
		backup_port = get_system_backup_port(sysid['id'])

		if backup_port is None:
			try:
				backup_port = register_system_backup_port(sysid['id'])
			except Exception as ex:
				app.logger.debug("api_v1_register: failed to register system backup port " + str(type(ex)) + " - " + str(ex))
				return jsonify({'error': True, 'reason': "The server was unable to assign a backup port number"})
		else:
			app.logger.info("api_v1_register: Reusing existing allocated backup port number for " + hostname)

	## create an event to say the system was registered
	curd.execute("INSERT INTO `systems_events` (`sid`, `name`, `when`, `status`, `data`) VALUES (%s,'register',NOW(),0,%s)", (sysid['id'],username,))
	g.db.commit()

	app.logger.info("api_v1_register: registration complete for " + hostname + " using account " + username)
	return jsonify({'private_key': private_key_str, 'public_key': public_key_str, 'backup_key': backup_key, 'backup_port': backup_port, 'api_key': api_key})

################################################################################
# update data 
@app.route('/api/v1/update/metadata', methods=['POST'])
@app.register_api_function
def api_v1_update_metadata():
	"""REST API endpoint to allow workstations to describe their details to the server"""
	## check machine authentication and get the resulting system object
	system = system_api_auth()

	## get the json data tlob
	metadata = request.form['metadata']

	## check what we're given is actually valid JSON
	try:
		metadata_load = json.loads(metadata)
	except Exception as ex:
		app.logger.info("api_v1_update_metadata: Authenticated machine " + system['name'] + " presented invalid JSON")
		app.logger.debug(metadata)
		return stderr("Invalid JSON data","The 'data' parameter must be valid JSON",code=400)

	else:
		## try to extract the package list
		try:
			packages = metadata_load['packages']
			del(metadata_load['packages'])
			#reflatten the struct
			metadata = json.dumps(metadata_load)
		except KeyError:
			packages = None
			pass

	## update the database
	curd = g.db.cursor(mysql.cursors.DictCursor)
	curd.execute('INSERT INTO `systems_data` (`sid`, `metadata`) VALUES (%s,%s) ON DUPLICATE KEY UPDATE `metadata` = %s', (system['id'],metadata,metadata,))
	## update the system packages
	if packages is not None:
		curd.execute('DELETE FROM `systems_packages` WHERE `sid` = %s', (system['id'],))
		for package in packages:
			curd.execute('INSERT INTO `systems_packages` (`sid`, `package`) VALUES (%s,%s)', (system['id'], package))

	## create an event to say the system updated it metadata
	curd.execute("INSERT INTO `systems_events` (`sid`, `name`, `when`, `status`) VALUES (%s,'update_metadata',NOW(),0)", (system['id'],))

	g.db.commit()

	## mark the system 'last seen at'
	system_api_checkin(system)

	return jsonify({"success": True})

@app.route('/api/v1/update/facts', methods=['POST'])
@app.register_api_function
def api_v1_update_facts():
	"""REST API endpoint to allow workstations to upload puppet facts"""
	## check machine authentication and get the resulting system object
	system = system_api_auth()

	## get the json data tlob
	facts = request.form['facts']

	## check what we're given is actually valid JSON
	try:
		json.loads(facts)
	except Exception as ex:
		app.logger.info("api_v1_update_facts: Authenticated machine " + system['name'] + " presented invalid JSON")
		app.logger.debug(facts)
		return stderr("Invalid JSON data","The 'data' parameter must be valid JSON",code=400)

	## update the database
	curd = g.db.cursor(mysql.cursors.DictCursor)
	curd.execute('INSERT INTO `systems_data` (`sid`, `facts`) VALUES (%s, %s) ON DUPLICATE KEY UPDATE `facts` = %s', (system['id'],facts,facts,))

	## create an event to say the system updated it facts
	curd.execute("INSERT INTO `systems_events` (`sid`, `name`, `when`, `status`) VALUES (%s,'update_facts',NOW(),0)", (system['id'],))

	g.db.commit()

	## mark the system 'last seen at'
	system_api_checkin(system)

	return jsonify({"success": True})

@app.route('/api/v1/update/status', methods=['POST'])
@app.register_api_function
def api_v1_update_status():
	"""REST API endpoint to allow workstations to update their backup/puppet/update status"""
	## check machine authentication and get the resulting system object
	system = system_api_auth()

	status_type = request.form['type']
	if status_type not in ['backup','puppet','update']:
		abort(400)
	else:
		status_field = status_type + "_status"

	## get the json data tlob
	jsondata = request.form['data']

	## check what we're given is actually valid JSON
	try:
		json.loads(jsondata)
	except Exception as ex:
		app.logger.info("api_v1_update_status: Authenticated machine " + system['name'] + " presented invalid JSON")
		return stderr("Invalid JSON data","The 'data' parameter must be valid JSON",code=400)

	## update the database
	curd = g.db.cursor(mysql.cursors.DictCursor)
	curd.execute("INSERT INTO `systems_data` (`sid`, `" + status_field + "`) VALUES (%s,%s) ON DUPLICATE KEY UPDATE `" + status_field + "` = %s", (system['id'],jsondata,jsondata,))

	## create an event to say the system updated it status
	curd.execute("INSERT INTO `systems_events` (`sid`, `name`, `when`, `status`, `data`) VALUES (%s,'update_status',NOW(),0,%s)", (system['id'],status_field))

	g.db.commit()

	## mark the system 'last seen at'
	system_api_checkin(system)

	return jsonify({"success": True})

# update data 
@app.route('/api/v1/event', methods=['POST'])
@app.register_api_function
def api_v1_event():
	"""REST API endpoint to allow workstations to register an event. Currently
	the events are sent in the parameter 'event' and the supported events are:
	- ping (machine is just checking in)
	- startup (machine has just started up)
	- shutdown (machine is being shut down)
	"""
	system = system_api_auth()

	event_name = request.form['event']

	if event_name not in ['ping','startup','shutdown']:
		abort(400)

	## update the database
	curd = g.db.cursor(mysql.cursors.DictCursor)
	curd.execute('INSERT INTO `systems_events` (`sid`, `name`, `when`, `status`) VALUES (%s,%s,NOW(),0)', (system['id'],event_name,))
	g.db.commit()

	## mark the system 'last seen at'
	system_api_checkin(system)

	return jsonify({"success": True})
