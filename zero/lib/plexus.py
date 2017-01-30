#!/usr/bin/python

from zero import app
from flask import g, flash
import Pyro4

def plexus_connect():
	try:
		plexus = Pyro4.Proxy('PYRO:plexus@./u:' + app.config('PLEXUS_SOCKET_PATH'))
		plexus._pyroTimeout = 10
		plexus.ping()
	except Exception as ex:
		raise app.FatalError("Unable to connect to the plexus daemon: " + str(ex))

	return plexus
