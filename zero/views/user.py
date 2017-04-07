#!/usr/bin/python

from zero import app
import zero.lib.user
from flask import Flask, request, session, redirect, url_for, flash, g, abort, render_template
import re
import grp
import cas

################################################################################

@app.route('/cas/redirect')
def cas_login():
	client = cas.CASClientV3(renew=False, extra_login_params=False, server_url=app.config['CAS_SERVER_URL'], service_url=url_for('cas_login_verify',_external=True))
	return redirect(client.get_login_url())

@app.route('/cas/login')
def cas_login_verify():
	client = cas.CASClientV3(renew=False, extra_login_params=False, server_url=app.config['CAS_SERVER_URL'], service_url=url_for('cas_login_verify',_external=True))
	if 'ticket' in request.args:
		(username, attributes, pgtiou) = client.verify_ticket(request.args['ticket'])

		if username is None:
			return redirect(client.get_login_url())
		else:
			username = username.lower()
			if not zero.lib.user.is_user_authorised(username):
				app.logger.info("User " + username + " tried to use the service, but they were not in linuxsys or linuxadm, rejecting")
				flash("You are not authorised to use this service, sorry!","alert-danger")
				return redirect(url_for('login'))

			# Logon is OK to proceed
			return zero.lib.user.logon_ok(username)

	else:
		abort(400)

@app.route('/login', methods=['GET', 'POST'])
def login():
	"""Handles the login page, logging a user in on correct authentication."""

	# If the user is already logged in, just redirect them
	if zero.lib.user.is_logged_in():
		return redirect(url_for('default'))
	else:
		# On GET requests
		if request.method == 'GET' or request.method == 'HEAD':
			next = request.args.get('next', default=None)
			return render_template('login.html', next=next)

		# On POST requests, authenticate the user
		elif request.method == 'POST':
			username = request.form['username'].lower()
			password = request.form['password']

			result = zero.lib.user.authenticate(username, password)

			if not result:
				flash('Incorrect username and/or password', 'alert-danger')
				return redirect(url_for('login'))

			if not zero.lib.user.is_user_authorised(username):
				app.logger.info("User " + username + " tried to use the service, but they were not in linuxsys or linuxadm, rejecting")
				flash("You are not authorised to use this service, sorry!","alert-danger")
				return redirect(url_for('login'))

			# Permanent sessions
			permanent = request.form.get('sec', default="")

			# Set session as permanent or not
			if permanent == 'sec':
				session.permanent = True
			else:
				session.permanent = False

			# Logon is OK to proceed
			return zero.lib.user.logon_ok(username)

################################################################################

@app.route('/logout')
@zero.lib.user.login_required
def logout():
	"""Logs a user out"""

	# Log out of the session
	zero.lib.user.clear_session()
	
	# Redirect the user to the login page
	return redirect(url_for('login'))
