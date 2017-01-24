#!/usr/bin/python

from deskctl import app
import deskctl.lib.user
from flask import Flask, request, session, redirect, url_for, flash, g, abort, render_template
import re

################################################################################

@app.route('/login', methods=['GET', 'POST'])
def login():
	"""Handles the login page, logging a user in on correct authentication."""
	app.logger.debug("login()")

	# If the user is already logged in, just redirect them
	if deskctl.lib.user.is_logged_in():
		return redirect(url_for('default'))
	else:
		# On GET requests, just go to the default page
		if request.method == 'GET' or request.method == 'HEAD':
			return redirect(url_for('default'))

		# On POST requests, authenticate the user
		elif request.method == 'POST':
			result = deskctl.lib.user.authenticate(request.form['username'], request.form['password'])

			if not result:
				flash('Incorrect username and/or password', 'alert-danger')
				return redirect(url_for('default'))
			
			# Set the username in the session
			session['username'] = request.form['username'].lower()
			session.permanent = True

			# If they have a place they want to go to after login
			if 'next' in request.form:
				session['next'] = request.form['next']

			# Logon is OK to proceed
			return deskctl.lib.user.logon_ok()

################################################################################

@app.route('/logout')
@deskctl.lib.user.login_required
def logout():
	"""Logs a user out"""
	app.logger.debug("logout()")

	# Log out of the session
	deskctl.lib.user.clear_session()
	
	# Tell the user
	flash('You were logged out successfully', 'alert-success')
	
	# Redirect the user to the login page
	return redirect(url_for('login'))
