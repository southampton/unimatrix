#!/usr/bin/python
# -*- coding: utf-8 -*-
import os
import os.path
from flask import Flask, request, session, abort, g, render_template, url_for
import logging
import binascii

class DeskCtlFlask(Flask):

	config_file = '/usr/lib/deskctl/deskctl.conf'

	class FatalError(Exception):
		pass

	class DaemonConnectionError(Exception):
		pass

	################################################################################

	def __init__(self, init_object_name):
		"""Constructor for the application. Reads the config, sets
		up logging, configures Jinja and Flask."""

		# Call the superclass (Flask) constructor
		super(DeskCtlFlask, self).__init__(init_object_name)

		# CSRF exemption support
		self._exempt_views = set()
		self.before_request(self._csrf_protect)

		# CSRF token function in templates
		self.jinja_env.globals['csrf_token'] = self._generate_csrf_token

		# Load the __init__.py config defaults
		self.config.from_object("deskctl.defaultcfg")

		# Check the config file exists, if it does not, create one instead
		# with a random secret key in it which we generate
		if not os.path.exists(self.config_file):
			app.logger.info("No config file found; generating new config file")
			try:
				with open(self.config_file,'w') as fp:
					fp.write('SECRET_KEY="' + self.token() + '"')

				os.chmod(self.config_file,0700)
			except Exception as ex:
				raise self.FatalError("Could not create new config file: " + str(ex))

		# Load the config file
		self.config.from_pyfile('/usr/lib/deskctl/deskctl.conf')

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

		# Set up the max log level
		if self.debug:
			self.logger.setLevel(logging.DEBUG)
		else:
			self.logger.setLevel(logging.INFO)

		# Output some startup info
		self.logger.info('deskctl version ' + self.config['VERSION'] + ' initialised')
		self.logger.info('debug status: ' + str(self.config['DEBUG']))

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
