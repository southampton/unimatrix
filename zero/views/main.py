#!/usr/bin/python

from zero import app
from zero.lib.user import is_logged_in
from flask import Flask, request, session, redirect, url_for, flash, g, abort, make_response, render_template, jsonify
import MySQLdb as mysql

################################################################################

@app.route('/')
def default():
	"""Renders the about page"""

	if is_logged_in():
		return render_template('error.html', title='welcome', message="You are currently logged in as " + session['username'])
	else:
		return redirect(url_for('login'))
