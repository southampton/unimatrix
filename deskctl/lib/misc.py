#!/usr/bin/python

from deskctl import app
import Pyro4

def deskctld_connect():
	try:
		deskctld = Pyro4.Proxy('PYRO:deskctld@./u:' + "/run/deskctld.sock")
		deskctld.ping()
	except Exception as ex:
		raise app.DaemonConnectionError("The detailed error was: " + str(ex))

	return deskctld
