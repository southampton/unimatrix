#!/usr/bin/python

from deskctl.app import DeskCtlFlask

app = DeskCtlFlask(__name__)

import deskctl.lib.user
import deskctl.request
import deskctl.views.errors
import deskctl.views.user
import deskctl.views.main
