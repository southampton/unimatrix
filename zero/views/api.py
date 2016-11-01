#!/usr/bin/python

from zero import app
from zero.lib.user import is_logged_in, authenticate, is_user_in_group
from flask import Flask, request, session, redirect, url_for, flash, g, abort, make_response, render_template, jsonify
import MySQLdb as mysql

################################################################################

@app.route('/api/register', methods=['POST'])
@app.disable_csrf_check
def api_register():
	"""Simple REST API endpoint to allow workstations to register"""

	username = request.form['username']
	#os_ident = request.form['ident']
	#hostname = request.form['hostname']
	#metadata = request.form['metadata']
	#facts    = request.form['facts']

	## Check username + password in LDAP
	result = authenticate(username, request.form['password'])

	if not result:
		app.logger.debug("New registration request failed due to authentication failure for " + username)
		abort(403)
	else:
		app.logger.info("New registration request from authenticated user " + username)

	## Only allow iSolutions staff to register systems
	if not is_user_in_group(username,"jfStaff"):
		abort(406)

	## Validate hostname if sent
	if 'hostname' in request.form:
		pass
	else:
		## Generate a hostname
		pass

	## Validate metadata

	## Check if the system was already registered

	return jsonify(['OK'])

