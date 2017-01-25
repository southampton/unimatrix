#!/usr/bin/python
# -*- coding: utf-8 -*-
from flask import Flask, request, session, abort, g, render_template, url_for
import jinja2 
import os.path
from os import walk
import imp
import random
import string
import logging
import os.path
from logging.handlers import SMTPHandler
from logging.handlers import RotatingFileHandler
from logging import Formatter
import MySQLdb as mysql
import traceback
import binascii

class ZeroFlask(Flask):

	class FatalError(Exception):
		pass

	################################################################################

	def __init__(self, init_object_name):
		"""Constructor for the application. Reads the config, sets
		up logging, configures Jinja and Flask."""

		# Call the superclass (Flask) constructor
		super(ZeroFlask, self).__init__(init_object_name)

		# CSRF exemption support
		self._exempt_views = set()
		self.before_request(self._csrf_protect)

		# CSRF token function in templates
		self.jinja_env.globals['csrf_token'] = self._generate_csrf_token

		# Load the __init__.py config defaults
		self.config.from_object("zero.defaultcfg")

		# Load system config file
		self.config.from_pyfile('/etc/unimatrix/zero.conf')

		# Check all the necessary options have been defined
		for cfg in ['SECRET_KEY']:
			error = False
			if not cfg in self.config:
				error = True
			else:
				if len(self.config[cfg]) == 0:
					error = True

			if error:
				raise ValueError("The configuration option '" + cfg + "' must be set")

		# Set up logging to file
		if self.config['FILE_LOG'] == True:
			file_handler = RotatingFileHandler(self.config['LOG_DIR'] + '/' + self.config['LOG_FILE'], 'a', self.config['LOG_FILE_MAX_SIZE'], self.config['LOG_FILE_MAX_FILES'])
			file_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s'))
			self.logger.addHandler(file_handler)

		# Set up the max log level
		if self.debug:
			self.logger.setLevel(logging.DEBUG)
			file_handler.setLevel(logging.DEBUG)
		else:
			self.logger.setLevel(logging.INFO)
			file_handler.setLevel(logging.INFO)

		# Output some startup info
		self.logger.info('unimatrix-zero version ' + self.config['VERSION'] + ' initialised')
		self.logger.info('debug status: ' + str(self.config['DEBUG']))

		# set up e-mail alert logging
		if self.config['EMAIL_ALERTS'] == True:
			# Log to file where e-mail alerts are going to
			self.logger.info('e-mail alerts are enabled and being sent to: ' + str(self.config['ADMINS']))

			# Create the mail handler
			mail_handler = SMTPHandler(self.config['SMTP_SERVER'], self.config['EMAIL_FROM'], self.config['ADMINS'], self.config['EMAIL_SUBJECT'])

			# Set the minimum log level (errors) and set a formatter
			mail_handler.setLevel(logging.ERROR)
			mail_handler.setFormatter(Formatter("""
A fatal error occured in unimatrix-zero.

Message type:       %(levelname)s
Location:           %(pathname)s:%(lineno)d
Module:             %(module)s
Function:           %(funcName)s
Time:               %(asctime)s
Logger Name:        %(name)s
Process ID:         %(process)d

Further Details:

%(message)s

"""))

			self.logger.addHandler(mail_handler)

		# Debug Toolbar
		if self.config['DEBUG_TOOLBAR']:
			self.debug = True
			from flask_debugtoolbar import DebugToolbarExtension
			toolbar = DebugToolbarExtension(app)
			self.logger.info('debug toolbar enabled - DO NOT USE THIS ON LIVE SYSTEMS!')

		# check the database is up and is working
		self.init_database()

	################################################################################

	def token(self,bytes=64):
		"""Generates a random token. This code was derived from the
			proposed new 'token' functions in Python 3.6, see:
			https://bitbucket.org/sdaprano/secrets/"""

		return binascii.hexlify(os.urandom(bytes))

	################################################################################

	def _generate_csrf_token(self):
		"""This function is used to generate a CSRF token for use in templates."""

		if '_csrf_token' not in session:
			session['_csrf_token'] = self.token()

		return session['_csrf_token']

	################################################################################

	def _csrf_protect(self):
		"""Performs the checking of CSRF tokens. This check is skipped for the 
		GET, HEAD, OPTIONS and TRACE methods within HTTP, and is also skipped
		for any function that has been added to _exempt_views by use of the
		disable_csrf_check decorator."""

		## Throw away requests with methods we don't support
		if request.method not in ('GET', 'HEAD', 'POST'):
			abort(405)

		# For methods that require CSRF checking
		if request.method == 'POST':
			view = self.view_functions.get(request.endpoint)

			# Make sure we actually found a view function
			if view is not None:
				view_location = view.__module__ + '.' + view.__name__

				# If the view is not exempt
				if not view_location in self._exempt_views:
					token = session.get('_csrf_token')
					if not token or token != request.form.get('_csrf_token'):
						if 'username' in session:
							self.logger.warning('CSRF protection alert: %s failed to present a valid POST token', session['username'])
						else:
				 			self.logger.warning('CSRF protection alert: a non-logged in user failed to present a valid POST token')

						# The user should not have accidentally triggered this so just throw a 400
						abort(400)

				else:
					self.logger.debug('View ' + view_location + ' is exempt from CSRF checks')

	################################################################################

	def disable_csrf_check(self, view):
		"""A decorator that can be used to exclude a view from CSRF validation.
		Example usage of disable_csrf_check might look something like this:
			@app.disable_csrf_check
			@app.route('/some_view')
			def some_view():
				return render_template('some_view.html')
		:param view: The view to be wrapped by the decorator.
		"""

		view_location = view.__module__ + '.' + view.__name__
		self._exempt_views.add(view_location)
		self.logger.debug('Added CSRF check exemption for ' + view_location)
		return view

	################################################################################

	def log_exception(self, exc_info):
		"""Logs an exception.  This is called by :meth:`handle_exception`
		if debugging is disabled and right before the handler is called.
		This implementation logs the exception as an error on the
		:attr:`logger` but sends extra information such as the remote IP
		address, the username, etc. This extends the default implementation
		in Flask.

		"""

		if 'username' in session:
			usr = session['username']
		else:
			usr = 'Not logged in'

		self.logger.error("""Path:                 %s 
HTTP Method:          %s
Client IP Address:    %s
User Agent:           %s
User Platform:        %s
User Browser:         %s
User Browser Version: %s
Username:             %s
""" % (
			request.path,
			request.method,
			request.remote_addr,
			request.user_agent.string,
			request.user_agent.platform,
			request.user_agent.browser,
			request.user_agent.version,
			usr,
			
		), exc_info=exc_info)

################################################################################

	def init_database(self):
		"""Ensures the app can talk to the database (rather than waiting for a HTTP
		connection to trigger before_request) and the tables are there. Only runs
		at app startup."""

		# Connect to database
		try:
			temp_db = mysql.connect(host=self.config['MYSQL_HOST'], port=self.config['MYSQL_PORT'], user=self.config['MYSQL_USER'], passwd=self.config['MYSQL_PASS'], db=self.config['MYSQL_NAME'])
		except Exception as ex:
			raise Exception("Could not connect to MySQL server: " + str(type(ex)) + " - " + str(ex))

		self.logger.info("Successfully connected to the MySQL database server")

		## Now create tables if they don't exist
		cursor = temp_db.cursor()

		## Turn on autocommit so each table is created in sequence
		cursor.connection.autocommit(True)

		## Turn off warnings (MySQLdb generates warnings even though we use IF NOT EXISTS- wtf?!)
		cursor._defer_warnings = True

		self.logger.info("Checking for and creating tables as necessary")

		cursor.execute("""CREATE TABLE IF NOT EXISTS `systems` (
		  `id` mediumint(11) NOT NULL AUTO_INCREMENT,
		  `name` varchar(255) NOT NULL,
		  `create_date` datetime DEFAULT NULL,
		  `register_date` datetime DEFAULT NULL,
		  `last_seen_date` datetime DEFAULT NULL,
          `ssh_public_key` TEXT,
          `backup_key` varchar(128),
          `api_key` varchar(128),
		  PRIMARY KEY (`id`),
		  KEY `name` (`name`(255))
		) ENGINE=InnoDB DEFAULT CHARSET=utf8;""")

		cursor.execute("""CREATE TABLE IF NOT EXISTS `systems_backup_ports` (
		  `port` mediumint(11) NOT NULL,
		  `sid` mediumint(11),
          PRIMARY KEY(port),
          CONSTRAINT `systems_link` FOREIGN KEY (`sid`) REFERENCES `systems` (`id`) ON DELETE SET NULL ON UPDATE SET NULL
		) ENGINE=InnoDB DEFAULT CHARSET=utf8;""")

		cursor.execute("""CREATE TABLE IF NOT EXISTS `ldap_group_cache` (
		 `username` varchar(64) NOT NULL,
		 `group` varchar(255) NOT NULL,
		  PRIMARY KEY (`username`, `group`)
		) ENGINE=InnoDB DEFAULT CHARSET=utf8""")

		cursor.execute("""CREATE TABLE IF NOT EXISTS `ldap_group_cache_expire` (
		 `username` varchar(64) NOT NULL,
		 `expiry_date` datetime DEFAULT NULL,
		  PRIMARY KEY (`username`)
		) ENGINE=InnoDB DEFAULT CHARSET=utf8""")

		cursor.execute("""CREATE TABLE IF NOT EXISTS `tasks` (
		  `id` mediumint(11) NOT NULL AUTO_INCREMENT,
		  `sid` mediumint(11) NOT NULL,
		  `name` varchar(255) NOT NULL,
		  `start` datetime NOT NULL,
		  `end` datetime DEFAULT NULL,
		  `status` tinyint(4) NOT NULL DEFAULT '-1',
          `result` TEXT,
		  PRIMARY KEY (`id`),
		  CONSTRAINT `tasks_ibfk_1` FOREIGN KEY (`sid`) REFERENCES `systems` (`id`) ON DELETE CASCADE
		) ENGINE=InnoDB DEFAULT CHARSET=utf8;""")

		cursor.execute("""CREATE TABLE IF NOT EXISTS `pkg_categories` (
		  `id` mediumint(11) NOT NULL AUTO_INCREMENT,
		  `name` varchar(255) NOT NULL,
		  PRIMARY KEY (`id`),
		) ENGINE=InnoDB DEFAULT CHARSET=utf8;""")

		cursor.execute("""CREATE TABLE IF NOT EXISTS `pkg_entries` (
		  `id` mediumint(11) NOT NULL AUTO_INCREMENT,
		  `pkg_category_id` mediumint(11) NOT NULL,
		  `name` varchar(255) NOT NULL,
		  `desc` TEXT,
		  `icon` varchar(255) NOT NULL,
		  PRIMARY KEY (`id`),
		  CONSTRAINT `pkg_entries_ibfk_1` FOREIGN KEY (`pkg_category_id`) REFERENCES `pkg_categories` (`id`) ON DELETE CASCADE
		) ENGINE=InnoDB DEFAULT CHARSET=utf8;""")

		cursor.execute("""CREATE TABLE IF NOT EXISTS `pkg_entry_items` (
		  `id` mediumint(11) NOT NULL AUTO_INCREMENT,
		  `pkg_entry_id` mediumint(11) NOT NULL,
		  `name` varchar(255) NOT NULL,
		  PRIMARY KEY (`id`),
		  CONSTRAINT `pkg_entry_actions_ibfk_1` FOREIGN KEY (`pkg_entry_id`) REFERENCES `pkg_entries` (`id`) ON DELETE CASCADE
		) ENGINE=InnoDB DEFAULT CHARSET=utf8;""")

		## Close database connection
		temp_db.close()

		self.logger.info("Database initialisation complete")
