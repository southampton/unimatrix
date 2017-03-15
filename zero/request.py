from zero import app
from zero.lib.errors import logerr, fatalerr
from zero.lib.user import is_logged_in
from flask import Flask, request, session, g, abort, render_template, url_for
import MySQLdb as mysql
import datetime
import json

################################################################################

@app.before_request
def before_request():
	try:
		g.db = mysql.connect(host=app.config['MYSQL_HOST'], port=app.config['MYSQL_PORT'], user=app.config['MYSQL_USER'], passwd=app.config['MYSQL_PASS'], db=app.config['MYSQL_NAME'], charset="utf8")
	except Exception as ex:
		logerr()
		return fatalerr(message='Could not connect to the MySQL/MariaDB server')

	app.jinja_env.globals['is_logged_in'] = is_logged_in

################################################################################

@app.template_filter('ut2str')
def jinja_filter_ut2str(ut):
	if type(ut) is int:
		return datetime.datetime.fromtimestamp(int(ut)).strftime('%Y-%m-%d %H:%M:%S %Z')
	elif type(ut) is datetime.datetime:
		return ut.strftime('%Y-%m-%d %H:%M:%S %Z')
	else:
		return ut

################################################################################

@app.template_filter('obj2json')
def jinja_filter_obj2json(data):
	return json.dumps(data,indent=4)
