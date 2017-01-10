#!/usr/bin/python
from datetime import timedelta

VERSION='0.1'

## Debug mode. This engages the web-based debug mode
DEBUG = False

# Key used to sign/encrypt session data stored in cookies.
SECRET_KEY = ''

## Flask defaults (changed to what we prefer)
SESSION_COOKIE_SECURE      = False
SESSION_COOKIE_HTTPONLY    = False
PREFERRED_URL_SCHEME       = 'http'
PERMANENT_SESSION_LIFETIME = timedelta(days=30)
