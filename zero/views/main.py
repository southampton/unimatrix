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

			try:
				order = 1
				for catid in newOrderList:
					curd.execute("UPDATE `pkg_categories` SET `order` = %s WHERE `id` = %s",(order,int(catid)))
					order = order + 1
				g.db.commit()
			except Exception as ex:
				app.logger.error("Failed to update category order in database: " + str(type(ex)) + " - " + str(ex))
				abort(500)

			# regenerate the pkgdb with the new order
			try:
				plexus = plexus_connect()
				plexus.regenerate_pkgdb()
			except Exception as ex:
				app.logger.error("Failed to regenerate the pkgdb: " + str(type(ex)) + " - " + str(ex))
				abort(500)

			return "", 200

		elif action == 'new':
			# new order is a json string of an array
			catname = request.form['name']
			curd.execute("INSERT INTO `pkg_categories` (`name`,`order`) VALUES (%s,999)",(catname,))
			g.db.commit()

			flash("New category added","alert-success")
			return redirect(url_for('pkgdb_categories'))

		else:
			abort(400)
