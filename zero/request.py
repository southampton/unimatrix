from zero import app
from zero.lib.errors import logerr, fatalerr
from zero.lib.user import is_logged_in
from flask import Flask, request, session, g, abort, render_template, url_for
import MySQLdb as mysql

################################################################################

@app.before_request
def before_request():
	try:
		g.db = mysql.connect(host=app.config['MYSQL_HOST'], port=app.config['MYSQL_PORT'], user=app.config['MYSQL_USER'], passwd=app.config['MYSQL_PASS'], db=app.config['MYSQL_NAME'], charset="utf8")
	except Exception as ex:
		logerr()
		return fatalerr(message='Could not connect to the MySQL/MariaDB server')

	app.jinja_env.globals['is_logged_in'] = is_logged_in
