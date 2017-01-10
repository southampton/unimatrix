from deskctl import app
from deskctl.lib.errors import logerr, fatalerr
from deskctl.lib.user import is_logged_in
from flask import Flask, request, session, g, abort, render_template, url_for
import MySQLdb as mysql

################################################################################

@app.before_request
def before_request():
	app.jinja_env.globals['is_logged_in'] = is_logged_in
