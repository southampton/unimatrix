#!/usr/bin/python

from zero import app
from zero.lib.user import is_logged_in, authenticate, is_user_in_group
from flask import Flask, request, session, redirect, url_for, flash, g, abort, make_response, render_template, jsonify
import MySQLdb as mysql
import re

####
from paramiko import RSAKey
####
import StringIO
####

################################################################################

@app.route('/api/register', methods=['POST'])
@app.disable_csrf_check
def api_register():
	"""Simple REST API endpoint to allow workstations to register"""

	app.logger.debug("call: api_register()")

	## We return 200 OK whatever errors we encounter
	## we return JSON, and if there is an error
	## the JSON has an 'error' variable set with the problem

	username = request.form['username']
	#os_ident = request.form['ident']
	#metadata = request.form['metadata']
	#facts    = request.form['facts']

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

	## TODO Validate metadata

	## TODO check facts

	## TODO Check if the system was already registered

	## Generate an SSH RSA private key
	private_key = RSAKey.generate(bits=2048)
	fakefile    = StringIO.StringIO()
	private_key.write_private_key(fakefile)

	## Reseek to 0 in our fake StringIO file
	fakefile.seek(0)

	## Generate an SSH RSA public key
	public_key = RSAKey.from_private_key(fakefile)

	## Turn it into a more usual output format
	public_key_str = public_key.get_name() + " " + public_key.get_base64()

	app.logger.debug("api_register: registration succeeded for " + hostname + " using account " + username)
	return jsonify({'private_key': fakefile.getvalue(), 'public_key': public_key_str})





