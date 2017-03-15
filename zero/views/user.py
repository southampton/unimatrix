#!/usr/bin/python

from zero import app
import zero.lib.user
from flask import Flask, request, session, redirect, url_for, flash, g, abort, render_template
import re
import grp

################################################################################

@app.route('/login', methods=['GET', 'POST'])
def login():
	"""Handles the login page, logging a user in on correct authentication."""

	# If the user is already logged in, just redirect them
	if zero.lib.user.is_logged_in():
		return redirect(url_for('default'))
	else:
		# On GET requests, just render the login page
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

			## Check they are authorised to login
			linuxsys = []
			linuxadm = []
			try:
				linuxsys = grp.getgrnam("linuxsys").gr_mem 
				linuxadm = grp.getgrnam("linuxadm").gr_mem
			except Exception as ex:
				pass 

			app.logger.info(str(linuxsys))
			app.logger.info(str(linuxadm))

			authorised = False
			if username in linuxsys or username in linuxadm:
				authorised = True

			if not authorised:
				app.logger.info("User " + username + " tried to use the service, but they were not in linuxsys or linuxadm, rejecting")
				flash("You are not authorised to use this service, sorry!","alert-danger")
				return redirect(url_for('login'))

			# Set the username in the session
			session['username']  = username 

			# Permanent sessions
			permanent = request.form.get('sec', default="")

			# Set session as permanent or not
			if permanent == 'sec':
				session.permanent = True
			else:
				session.permanent = False

			# Cache user groups
			try:
				zero.lib.user.get_users_groups(username,from_cache=False)
			except Exception as ex:
				pass

			# Logon is OK to proceed
			return zero.lib.user.logon_ok()

################################################################################

@app.route('/logout')
@zero.lib.user.login_required
def logout():
	"""Logs a user out"""

	# Log out of the session
	zero.lib.user.clear_session()
	
	# Redirect the user to the login page
	return redirect(url_for('login'))
