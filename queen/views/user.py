#!/usr/bin/python

from queen import app
import queen.lib.user
from flask import Flask, request, session, redirect, url_for, flash, g, abort, render_template
import re

################################################################################

@app.route('/login', methods=['GET', 'POST'])
def login():
	"""Handles the login page, logging a user in on correct authentication."""
	app.logger.debug("login()")

	# If the user is already logged in, just redirect them
	if queen.lib.user.is_logged_in():
		return redirect(url_for('default'))
	else:
		# On GET requests, just go to the default page
		if request.method == 'GET' or request.method == 'HEAD':
			return redirect(url_for('default'))

		# On POST requests, authenticate the user
		elif request.method == 'POST':
			result = queen.lib.user.authenticate(request.form['username'], request.form['password'])

			if not result:
				flash('Incorrect username and/or password', 'alert-danger')
				return redirect(url_for('default'))
			
			# Set the username in the session
			session['username'] = request.form['username'].lower()
			session.permanent = True

			# Logon is OK to proceed
			return queen.lib.user.logon_ok()

################################################################################

@app.route('/logout')
@queen.lib.user.login_required
def logout():
	"""Logs a user out"""
	app.logger.debug("logout()")

	# Log out of the session
	queen.lib.user.clear_session()
	
	# Tell the user
	flash('You were logged out successfully', 'alert-success')
	
	# Redirect the user to the login page
	return redirect(url_for('login'))
