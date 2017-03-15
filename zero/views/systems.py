#!/usr/bin/python

from zero import app
import zero.lib.user
from zero.lib.user import is_logged_in
from zero.lib.systems import get_system_by_name
from zero.lib.plexus import plexus_connect
from flask import Flask, request, session, redirect, url_for, flash, g, abort, make_response, render_template, jsonify
import MySQLdb as mysql
import json

@app.route('/systems')
@zero.lib.user.login_required
def systems():
	"""Renders the list of systems"""

	curd = g.db.cursor(mysql.cursors.DictCursor)
	curd.execute("""SELECT 
       `systems`.`id` AS `id`, 
       `systems`.`name` AS `name`, 
       `systems`.`create_date` AS `create_date`,
       `systems`.`register_date` AS `register_date`,
       `systems`.`last_seen_date` AS `last_seen_date`,
       `systems`.`last_seen_addr` AS `last_seen_addr`,
       `systems_data`.`facts` AS `facts`,
       `systems_data`.`metadata` AS `metadata`,
       `systems_data`.`backup_status` AS `backup_status`,
       `systems_data`.`update_status` AS `update_status`,
       `systems_data`.`puppet_status` AS `puppet_status`
       FROM `systems` 
       LEFT JOIN `systems_data` 
       ON `systems`.`id` = `systems_data`.`sid`""")

	systems = curd.fetchall()

	## decode json
	for system in systems:
		try:
			system['facts'] = json.loads(system['facts'])
		except Exception as ex:
			system['facts'] = None

		try:
			system['metadata'] = json.loads(system['metadata'])
		except Exception as ex:
			system['metadata'] = None

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

					system['metadata']['hwinfo']['sys'] = system['metadata']['hwinfo']['sys'].replace('Intel Corporation','Intel')

		try:
			system['backup_status'] = json.loads(system['backup_status'])
		except Exception as ex:
			system['backup_status'] = None

		try:
			system['update_status'] = json.loads(system['update_status'])
		except Exception as ex:
			system['update_status'] = None

		try:
			system['puppet_status'] = json.loads(system['puppet_status'])
		except Exception as ex:
			system['puppet_status'] = None

	return render_template('systems/systems.html',active="systems",systems=systems)

@app.route('/sys/<name>')
@zero.lib.user.login_required
def system(name):
	"""Shows information about a registered system"""

	system = get_system_by_name(name)

	if system is None:
		abort(404)
	else:
		return render_template("systems/system.html",system=system)
