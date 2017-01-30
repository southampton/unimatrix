#!/usr/bin/python

from zero import app
import zero.lib.user
from zero.lib.user import is_logged_in
from flask import Flask, request, session, redirect, url_for, flash, g, abort, make_response, render_template, jsonify
import MySQLdb as mysql

################################################################################

@app.route('/')
def default():
	"""Renders the about page"""

	if is_logged_in():
		return render_template('default.html')
	else:
		return redirect(url_for('login'))


@zero.lib.user.login_required
@app.route('/pkgdb/categories')
def pkgdb_categories():
	curd = g.db.cursor(mysql.cursors.DictCursor)
	curd.execute("SELECT * FROM `pkg_categories` ORDER BY `order`")
	categories = curd.fetchall()

	return render_template('pkgdb/categories.html',active="pkgdb_categories",categories=categories)
