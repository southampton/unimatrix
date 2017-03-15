#!/usr/bin/python

from zero import app
import zero.lib.ldapc
from flask import Flask, request, session, redirect, url_for, flash, g, abort, make_response, render_template, jsonify
import os 
import re
import pwd
import MySQLdb as mysql
from functools import wraps
from werkzeug.urls import url_encode

################################################################################

def login_required(f):
	"""This is a decorator function that when called ensures the user has logged in.
	Usage is as such: @zero.lib.user.login_required"""

	@wraps(f)
	def decorated_function(*args, **kwargs):
		if not is_logged_in():
			flash('You must login first!', 'alert-danger')
			args = url_encode(request.args)
			return redirect(url_for('login', next=request.script_root + request.path + "?" + args))
		return f(*args, **kwargs)
	return decorated_function

################################################################################

def is_logged_in():
	"""Returns a boolean indicating whether the current session has a logged
	in user."""

	return session.get('logged_in', False)

################################################################################

def clear_session():
	"""Ends the logged in user's login session. The session remains but it 
	is marked as being not logged in."""

	app.logger.info('User "' + session['username'] + '" logged out from "' + request.remote_addr + '" using ' + request.user_agent.string)

	# Remove the following items from the session
	session.pop('logged_in', None)
	session.pop('username', None)
	session.pop('id', None)


################################################################################

def logon_ok(): 
	"""This function is called post-logon or post TOTP logon to complete the
	logon sequence"""

	# Mark as logged on
	session['logged_in'] = True

	# Log a successful login
	app.logger.info('User "' + session['username'] + '" logged in from "' + request.remote_addr + '" using ' + request.user_agent.string)

	# Determine if "next" variable is set (the URL to be sent to)
	next = request.form.get('next', default=None)
	
	if next == None:
		return redirect(url_for('default'))
	else:
		return redirect(next)

################################################################################
# Authentication

def authenticate(username, password):
	"""Determines whether the given username and password combo is valid."""

	if len(username) == 0:
		return False
	if len(password) == 0:
		return False

	return zero.lib.ldapc.auth(username,password)

################################################################################

def get_users_groups(username, from_cache=True):
	"""Returns a set (not a list) of groups that a user belongs to. The result is 
	cached to improve performance and to lessen the impact on the LDAP server. The 
	results are returned from the cache unless you set "from_cache" to be 
	False. 

	This function will return None in all cases where the user was not found
	or where the user has no groups. It is not expeceted that a user will ever
	be in no groups, and if they are, then they probably shouldn't be using zero.
	"""

	if from_cache == False:
		return zero.lib.ldapc.get_users_groups_from_ldap(username)
	else:
		curd = g.db.cursor(mysql.cursors.DictCursor)

		## Get from the cache (if it hasn't expired)
		curd.execute('SELECT 1 FROM `ldap_group_cache_expire` WHERE `username` = %s AND `expiry_date` > NOW()', (username,))
		if curd.fetchone() is not None:
			app.logger.debug("Using cached results for LDAP user groups for user " + username)
			## The cache has not expired, return the list
			curd.execute('SELECT `group` FROM `ldap_group_cache` WHERE `username` = %s', (username,))
			groupdict = curd.fetchall()
			groups = []
			for group in groupdict:
				groups.append(group['group'])

			return groups

		else:
			app.logger.debug("Cached results expired or don't exist for " + username)
			## teh cache has expired, return them from LDAP directly (but also cache again)
			return zero.lib.ldapc.get_users_groups_from_ldap(username)

################################################################################

def is_user_in_group(username,group,from_cache=True):
	groups = get_users_groups(username,from_cache=from_cache)
	if group.lower() in groups:
		return True

	return False
