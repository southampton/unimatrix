#!/usr/bin/python

from queen.app import QueenFlask

app = QueenFlask(__name__)

import queen.lib.user
import queen.request
import queen.views.errors
import queen.views.user
import queen.views.main
