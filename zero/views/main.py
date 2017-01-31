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
		return render_template('default.html',active="default")
	else:
		return redirect(url_for('login'))


@zero.lib.user.login_required
@app.route('/pkgdb/categories',methods=['GET','POST'])
def pkgdb_categories():
	curd = g.db.cursor(mysql.cursors.DictCursor)

	if request.method == 'GET':
		curd.execute("SELECT * FROM `pkg_categories` ORDER BY `order`")
		categories = curd.fetchall()

		return render_template('pkgdb/categories.html',active="pkgdb",categories=categories)

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

			## TODO do some sort of validation on the name

			curd.execute("INSERT INTO `pkg_categories` (`name`,`order`) VALUES (%s,999)",(catname,))
			g.db.commit()

			flash("New category added","alert-success")
			return redirect(url_for('pkgdb_categories'))

		else:
			abort(400)

@zero.lib.user.login_required
@app.route('/pkgdb/category/<int:catid>',methods=['GET','POST'])
def pkgdb_category(catid):
	curd = g.db.cursor(mysql.cursors.DictCursor)
	curd.execute("SELECT * FROM `pkg_categories` WHERE `id` = %s",(catid,))
	category = curd.fetchone()

	if category is None:
		abort(404)

	if request.method == 'GET':
		curd.execute("SELECT * FROM `pkg_entries` WHERE `pkg_category_id` = %s ORDER BY `name`",(catid,))
		entries = curd.fetchall()
		return render_template('pkgdb/category.html',active="pkgdb",category=category,entries=entries)

	elif request.method == 'POST':
		action = request.form['action']

		if action == 'add':
			name  = request.form['name']
			desc  = request.form['desc']
			icon  = request.form['icon']
			items = request.form['items']

			## TODO VALIDATION TODO

			curd.execute("INSERT INTO `pkg_entries` (`pkg_category_id`,`name`,`desc`,`icon`) VALUES (%s, %s, %s, %s)",(category['id'],name,desc,icon,))
			g.db.commit()
			new_pkg_id = curd.lastrowid

			item_list = items.split("\r\n")
			for item in item_list:
				if len(item) > 0:
					curd.execute("INSERT INTO `pkg_entry_items` (`pkg_entry_id`,`name`) VALUES (%s, %s)",(new_pkg_id,item,))
					g.db.commit()

			flash("Package added to category","alert-success")
			return redirect(url_for("pkgdb_category",catid=category['id']))

		elif action == 'delete':
			curd.execute("DELETE FROM `pkg_categories` WHERE `id` = %s",(category['id'],))
			g.db.commit()

			flash("Category deleted","alert-success")
			return redirect(url_for("pkgdb_categories"))

@zero.lib.user.login_required
@app.route('/pkgdb/entry/<int:eid>',methods=['GET','POST'])
def pkgdb_entry(eid):
	curd = g.db.cursor(mysql.cursors.DictCursor)
	curd.execute("SELECT * FROM `pkg_entries` WHERE `id` = %s",(eid,))
	entry = curd.fetchone()

	if entry is None:
		abort(404)

	## Get the category name, for display purposes
	curd.execute("SELECT `id`, `name` FROM `pkg_categories` WHERE `id` = %s",(entry['pkg_category_id'],))
	category = curd.fetchone()

	## Get the items associated with this package entry
	curd.execute("SELECT * FROM `pkg_entry_items` WHERE `pkg_entry_id` = %s",(eid,))
	items = curd.fetchall()
	if request.method == 'GET':
		items_str = ""
		for item in items:
			items_str = items_str + item['name'] + "\r\n"

		return render_template('pkgdb/entry.html',active="pkgdb",entry=entry,items=items_str,category=category)

	elif request.method == 'POST':
		action = request.form['action']

		if action == 'edit':

			name  = request.form['name']
			desc  = request.form['desc']
			icon  = request.form['icon']
			items = request.form['items']

			## TODO VALIDATION TODO

			curd.execute("UPDATE `pkg_entries` SET `name` = %s, `desc` = %s, `icon` = %s WHERE `id` = %s",(name,desc,icon,entry['id'],))
			curd.execute("DELETE FROM `pkg_entry_items` WHERE `pkg_entry_id` = %s",(entry['id'],))
			g.db.commit()

			item_list = items.split("\r\n")
			for item in item_list:
				if len(item) > 0:
					curd.execute("INSERT INTO `pkg_entry_items` (`pkg_entry_id`,`name`) VALUES (%s, %s)",(entry['id'],item,))
					g.db.commit()

			flash("Package details updated and saved","alert-success")
			return redirect(url_for("pkgdb_entry",eid=entry['id']))

		elif action == 'delete':
			curd.execute("DELETE FROM `pkg_entries` WHERE `id` = %s",(entry['id'],))
			g.db.commit()

			flash("Package deleted","alert-success")
			return redirect(url_for("pkgdb_category",catid=entry['pkg_category_id']))
