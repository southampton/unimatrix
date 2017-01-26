#!/usr/bin/python

from deskctl import app
from flask import Flask, request, session, redirect, url_for, flash, g, abort, make_response, render_template, jsonify
import os 
import re
import pwd
from functools import wraps
from werkzeug.urls import url_encode
import pam
import pwd
import grp

################################################################################

def can_user_remove_software():
	if not is_logged_in():
		return False

	try:
		linuxsys = grp.getgrnam('linuxsys')
		linuxadm = grp.getgrnam('linuxadm')
		localsys = grp.getgrnam('sys')
	except KeyError as ex:
		raise app.FatalError("Expected core groups do not exist on the system. Please contact ServiceLine for assistance")

	if session['username'] in linuxsys.gr_mem:
		return True
	elif session['username'] in linuxadm.gr_mem:
		return True
	elif session['username'] in localsys:
		return True

	return False

################################################################################

def login_required(f):
	"""This is a decorator function that when called ensures the user has logged in.
	Usage is as such: @deskctl.lib.user.login_required"""

	@wraps(f)
	def decorated_function(*args, **kwargs):
		if not is_logged_in():
			flash('You must login first!', 'alert-danger')
			args = url_encode(request.args)
			session['next'] = request.script_root + request.path + "?" + args
			return redirect(url_for('login'))
		return f(*args, **kwargs)
	return decorated_function

################################################################################

def is_logged_in():
	"""Returns a boolean indicating whether the current session has a logged
	in user."""
	app.logger.debug("is_logged_in()")

	return session.get('logged_in', False)

################################################################################

def clear_session():
	"""Ends the logged in user's login session. The session remains but it 
	is marked as being not logged in."""
	app.logger.debug("clear_session()")

	app.logger.info('User "' + session['username'] + '" logged out from "' + request.remote_addr + '" using ' + request.user_agent.string)

	# Remove the following items from the session
	session.pop('logged_in', None)
	session.pop('username', None)
	session.pop('id', None)

################################################################################

def logon_ok(): 
	"""This function is called post-logon or post TOTP logon to complete the
	logon sequence"""
	app.logger.debug("logon_ok()")

	# Mark as logged on
	session['logged_in'] = True

	# Get the user's real name out of nss
	try:
		userdata = pwd.getpwnam(session['username'])
		session['name'] = userdata.pw_gecos
	except KeyError as ex:
		session['name'] = session['username']

	# Log a successful login
	app.logger.info('User "' + session['username'] + '" logged in from "' + request.remote_addr + '" using ' + request.user_agent.string)
		
	if "next" in session:
		next = session['next']
		session['next'] = None

		if next == None:
			return redirect(url_for('default'))
		else:
			return redirect(next)
	else:
		return redirect(url_for('default'))

################################################################################
# Authentication

def authenticate(username, password):
	app.logger.debug("authenticate()")

	"""Determines whether the given username and password combo is valid."""

	if len(username) == 0:
		return False
	if len(password) == 0:
		return False

	pamsvc = pam.pam()
	return pamsvc.authenticate(username,password)
