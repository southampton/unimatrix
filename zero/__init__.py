#!/usr/bin/python

from zero.app import ZeroFlask

app = ZeroFlask(__name__)

import zero.lib.user
import zero.request
import zero.views.errors
import zero.views.user
import zero.views.main
import zero.views.api
