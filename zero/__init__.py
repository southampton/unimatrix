#!/usr/bin/python

from zero.app import ZeroFlask

app = ZeroFlask(__name__)

import zero.lib.user
import zero.request
import zero.views.errors
import zero.views.user
import zero.views.main
import zero.views.api
import zero.views.pkgdb
import zero.views.systems
import zero.views.backups
import zero.views.lookup
