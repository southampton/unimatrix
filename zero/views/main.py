#!/usr/bin/python

from zero import app
import zero.lib.user
from zero.lib.user import is_logged_in
from zero.lib.systems import get_system_by_name
from zero.lib.plexus import plexus_connect
from flask import Flask, request, session, redirect, url_for, flash, g, abort, make_response, render_template, jsonify
import MySQLdb as mysql
import json

################################################################################

@app.route('/')
def default():
	"""Renders the about page"""

	if is_logged_in():
		return render_template('default.html',active="default")
	else:
		return redirect(url_for('login'))
