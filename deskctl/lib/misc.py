#!/usr/bin/python

from deskctl import app
import Pyro4
import sqlite3

def deskctld_connect():
	try:
		deskctld = Pyro4.Proxy('PYRO:deskctld@./u:' + "/run/deskctld.sock")
		deskctld.ping()
	except Exception as ex:
		raise app.DaemonConnectionError("The detailed error was: " + str(ex))

	return deskctld

def open_pkgdb():
	try:
		conn = sqlite3.connect("/etc/soton/pkgdb.sqlite")
		conn.row_factory = sqlite3.Row
		return conn
	except Exception as ex:
		raise app.FatalError("Could not open the package database: " + str(type(ex)) + " - " + str(ex))
