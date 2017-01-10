from deskctl import app
from deskctl.lib.errors import logerr, fatalerr
from deskctl.lib.user import is_logged_in
from flask import Flask, request, session, g, abort, render_template, url_for
import platform

################################################################################

@app.context_processor
def context_processor():
    return {
		"is_logged_in": is_logged_in,
		"hostname": platform.node().upper(),
	}
