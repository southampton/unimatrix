#!/usr/bin/python

from zero import app
import zero.lib.user
from zero.lib.user import is_logged_in
from zero.lib.systems import get_system_by_name, get_system_events, get_system_backups
from zero.lib.plexus import plexus_connect
from flask import Flask, request, session, redirect, url_for, flash, g, abort, make_response, render_template, jsonify
import MySQLdb as mysql
import json

@app.route('/backups/active')
@zero.lib.user.login_required
def backups_active():
	curd = g.db.cursor(mysql.cursors.DictCursor)
	curd.execute("SELECT `tasks`.`id` AS `id`, `tasks`.`start` AS `start`, `systems`.`name` AS `sysname` FROM `tasks` LEFT JOIN `systems` ON `tasks`.`sid` = `systems`.`id` WHERE `tasks`.`name` = 'backup' AND `tasks`.`status` = -1")
	tasks = curd.fetchall()

	return render_template("backups/active.html",active="backups",tasks=tasks)

@app.route('/backups/recent')
@zero.lib.user.login_required
def backups_recent():
	curd = g.db.cursor(mysql.cursors.DictCursor)
	curd.execute("SELECT `tasks`.`id` AS `id`, `tasks`.`start` AS `start`, `tasks`.`end` AS `end`, `tasks`.`status` AS `status`, `systems`.`name` AS `sysname` FROM `tasks` LEFT JOIN `systems` ON `tasks`.`sid` = `systems`.`id` WHERE `tasks`.`name` = 'backup' AND `tasks`.`status` > -1 AND `tasks`.`end` BETWEEN NOW() - INTERVAL 7 DAY AND NOW()")
	tasks = curd.fetchall()

	return render_template("backups/recent.html",active="backups",tasks=tasks)

@app.route('/backup/<id>')
@zero.lib.user.login_required
def backup(id):
	curd = g.db.cursor(mysql.cursors.DictCursor)
	curd.execute("SELECT * FROM `tasks` WHERE `id` = %s",(id,))
	task = curd.fetchone()

	if task is None:
		abort(404)

	if task['name'] != "backup":
		abort(404)

	curd.execute("SELECT * FROM `systems` WHERE `id` = %s",(task['sid'],))
	system = curd.fetchone()

	return render_template("backups/backup.html",task=task,active="backups",system=system)
