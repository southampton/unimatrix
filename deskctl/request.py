from deskctl import app
from deskctl.lib.errors import logerr, fatalerr
from deskctl.lib.user import is_logged_in
from flask import Flask, request, session, g, abort, render_template, url_for
import platform
import grp

################################################################################

@app.context_processor
def context_processor():
	vboxexists = False
	try:
		grp.getgrnam("vboxusers")
		vboxexists = True
	except KeyError as ex:
		pass

	return {
		"is_logged_in": is_logged_in,
		"hostname": platform.node().upper(),
		"vboxexists": vboxexists,
	}
