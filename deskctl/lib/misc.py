#!/usr/bin/python

from deskctl import app
import os
import Pyro4
import sqlite3
import subprocess

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

def sysexec(command,shell=False,env={}):
	try:
		procenv = os.environ.copy()
		for key, value in env.iteritems():
			procenv[key] = value

		proc = subprocess.Popen(command,stdout=subprocess.PIPE, stderr=subprocess.STDOUT,shell=shell,env=procenv)
		(stdoutdata, stderrdata) = proc.communicate()
		if stdoutdata is None:
			stdoutdata = ""

		return (proc.returncode,str(stdoutdata))
	except Exception as ex:
		return (1,str(type(ex)) + " - " + str(ex))
