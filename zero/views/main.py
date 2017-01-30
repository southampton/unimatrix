#!/usr/bin/python

from zero import app
import zero.lib.user
from zero.lib.user import is_logged_in
from zero.lib.plexus import plexus_connect
from flask import Flask, request, session, redirect, url_for, flash, g, abort, make_response, render_template, jsonify
import MySQLdb as mysql
import json

################################################################################

@app.route('/')
def default():
	"""Renders the about page"""

	if is_logged_in():
		return render_template('default.html')
	else:
		return redirect(url_for('login'))


@zero.lib.user.login_required
@app.route('/pkgdb/categories',methods=['GET','POST'])
def pkgdb_categories():
	curd = g.db.cursor(mysql.cursors.DictCursor)

	if request.method == 'GET':
		curd.execute("SELECT * FROM `pkg_categories` ORDER BY `order`")
		categories = curd.fetchall()

		return render_template('pkgdb/categories.html',active="pkgdb_categories",categories=categories)

	elif request.method == 'POST':
		action = request.form['action']

		if action == 'update':
			# new order is a json string of an array
			neworder = request.form['neworder']
	
			try:
				newOrderList = json.loads(neworder)
			except Exception as ex:
				abort(400)

			order = 1
			for catid in newOrderList:
				curd.execute("UPDATE `pkg_categories` SET `order` = %s WHERE `id` = %s",(order,int(catid)))
				order = order + 1

			g.db.commit()

			# regenerate the pkgdb with the new order
			plexus = plexus_connect()
			plexus.regenerate_pkgdb()

			return "", 200

		elif action == 'new':
			abort(400)
		else:
			abort(400)
