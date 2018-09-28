#!/usr/bin/python

from zero import app
import zero.lib.user
from zero.lib.user import is_logged_in
from zero.lib.systems import get_system_by_name, get_system_events, get_system_backups, delete_system_by_name
from zero.lib.plexus import plexus_connect
from flask import Flask, request, session, redirect, url_for, flash, g, abort, make_response, render_template, jsonify
import MySQLdb as mysql
import json

@app.route('/systems')
@zero.lib.user.login_required
def systems():
	"""Renders the list of systems"""

	curd = g.db.cursor(mysql.cursors.DictCursor)
	curd.execute("""SELECT `name` FROM `systems`""")
	system_names = curd.fetchall()
	systems = []

	for sysname in system_names:
		system = get_system_by_name(sysname['name'])

		if system['metadata'] is None:
			system['metadata'] = {
				'hwinfo': { 'sys': 'Unknown', 'cpu': 'Unknown', 'gpu': 'Unknown'}
			}

		else:
			if 'hwinfo' in system['metadata']:
				if 'gpu' in system['metadata']['hwinfo']:
					if 'NVIDIA' in system['metadata']['hwinfo']['gpu']:
						system['metadata']['hwinfo']['gpu'] = "NVIDIA"
					if 'nvidia' in system['metadata']['hwinfo']['gpu']:
						system['metadata']['hwinfo']['gpu'] = "NVIDIA"
					if 'AMD' in system['metadata']['hwinfo']['gpu']:
						system['metadata']['hwinfo']['gpu'] = "AMD"
					if 'amd' in system['metadata']['hwinfo']['gpu']:
						system['metadata']['hwinfo']['gpu'] = "AMD"
					if 'ATI' in system['metadata']['hwinfo']['gpu']:
						system['metadata']['hwinfo']['gpu'] = "AMD"
					if 'Intel' in system['metadata']['hwinfo']['gpu']:
						system['metadata']['hwinfo']['gpu'] = "Intel"
					if 'INTEL' in system['metadata']['hwinfo']['gpu']:
						system['metadata']['hwinfo']['gpu'] = "Intel"
					if 'Matrox' in system['metadata']['hwinfo']['gpu']:
						system['metadata']['hwinfo']['gpu'] = "Matrox"
					if 'MATROX' in system['metadata']['hwinfo']['gpu']:
						system['metadata']['hwinfo']['gpu'] = "Matrox"
					if 'VMware' in system['metadata']['hwinfo']['gpu']:
						system['metadata']['hwinfo']['gpu'] = "VMware"
					if 'VirtualBox' in system['metadata']['hwinfo']['gpu']:
						system['metadata']['hwinfo']['gpu'] = "VirtualBox"

				if 'cpu' in system['metadata']['hwinfo']:
					system['metadata']['hwinfo']['cpu'] = system['metadata']['hwinfo']['cpu'].replace('Intel(R)','Intel')
					system['metadata']['hwinfo']['cpu'] = system['metadata']['hwinfo']['cpu'].replace('Xeon(R)','Xeon')
					system['metadata']['hwinfo']['cpu'] = system['metadata']['hwinfo']['cpu'].replace('Core(TM)','Core')
					system['metadata']['hwinfo']['cpu'] = system['metadata']['hwinfo']['cpu'].replace('Opteron(tm)','Opteron')
					system['metadata']['hwinfo']['cpu'] = system['metadata']['hwinfo']['cpu'].replace('CPU ','')
					system['metadata']['hwinfo']['cpu'] = system['metadata']['hwinfo']['cpu'].replace('Processor ','')

				if 'sys' in system['metadata']['hwinfo']:
					if 'VMware' in system['metadata']['hwinfo']['sys']:
						system['metadata']['hwinfo']['sys'] = "VMware"

					system['metadata']['hwinfo']['sys'] = system['metadata']['hwinfo']['sys'].replace('Dell Inc.','Dell')
					system['metadata']['hwinfo']['sys'] = system['metadata']['hwinfo']['sys'].replace('Intel Corporation','Intel')

		systems.append(system)

	return render_template('systems/systems.html',active="systems",systems=systems)

@app.route('/sys/<name>',methods=['GET','POST'])
@zero.lib.user.login_required
def system(name):
	"""Shows information about a registered system"""

	system = get_system_by_name(name)

	if system is None:
		abort(404)
	else:
		if request.method == 'GET':
			return render_template("systems/system.html",active="systems",system=system)

		elif request.method == 'POST':
			action = request.form['action']

			if action == 'delete':
				delete_system_by_name(name)
				flash('System deleted','alert-success')
				return redirect(url_for("systems"))

@app.route('/sys/<name>/metadata')
@zero.lib.user.login_required
def system_metadata(name):
	"""Shows metadata for a registered system"""

	system = get_system_by_name(name)

	if system is None:
		abort(404)
	else:
		return render_template("systems/metadata.html",active="systems",system=system)

@app.route('/sys/<name>/events')
@zero.lib.user.login_required
def system_events(name):
	"""Shows events for a registered system"""

	system = get_system_by_name(name,extended=False)

	if system is None:
		abort(404)
	else:
		## Get all events
		events = get_system_events(system['id'])
		return render_template("systems/events.html",active="systems",system=system,events=events)

@app.route('/sys/<name>/packages')
@zero.lib.user.login_required
def system_packages(name):
	"""Shows packages for a registered system"""

	system = get_system_by_name(name)

	if system is None:
		abort(404)
	else:
		return render_template("systems/packages.html",active="systems",system=system)

@app.route('/sys/<name>/backups')
@zero.lib.user.login_required
def system_backups(name):
	"""Shows backup logs for a registered system"""

	system = get_system_by_name(name,extended=False)

	if system is None:
		abort(404)
	else:
		## Get all backups
		backups = get_system_backups(system['id'])
		return render_template("systems/backups.html",active="systems",system=system,backups=backups)
