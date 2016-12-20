#!/usr/bin/python

from queen import app
from queen.lib.user import is_logged_in
from flask import Flask, request, session, redirect, url_for, flash, g, abort, make_response, render_template, jsonify
import MySQLdb as mysql

################################################################################

@app.route('/')
def default():
	app.logger.debug("default()")

	return render_template('dashboard.html', title='dashboard')
