#!/usr/bin/python

from zero import app
from flask import g, flash
import MySQLdb as mysql
import ldap, ldap.filter
import re

################################################################################

def connect():
	# Connect to LDAP and turn off referrals
	conn = ldap.initialize(app.config['LDAP_URI'])
	conn.set_option(ldap.OPT_REFERRALS, 0)

	 # Bind to the server either with anon or with a defined user/pass in the config
	try:
		if app.config['LDAP_ANON_BIND']:
			conn.simple_bind_s()
		else:
			conn.simple_bind_s( (app.config['LDAP_BIND_USER']), (app.config['LDAP_BIND_PW']) )
	except ldap.LDAPError as e:
		raise app.FatalError("Could not connect to the LDAP directory server")

	return conn

################################################################################

def auth(username,password):

	# Connect to the LDAP server
	l = connect()

	# Now search for the user object to bind as
	try:
		results = l.search_s(app.config['LDAP_SEARCH_BASE'], ldap.SCOPE_SUBTREE, (app.config['LDAP_USER_ATTRIBUTE']) + "=" + ldap.filter.escape_filter_chars(username))
	except ldap.LDAPError as e:
		return False

	# Handle the search results
	for result in results:
		dn	= result[0]
		attrs	= result[1]

		if dn == None:
			# No dn returned. Return false.
			return False
		else:
			# Found the DN. Yay! Now bind with that DN and the password the user supplied
			try:
				lauth = ldap.initialize(app.config['LDAP_URI'])
				lauth.set_option(ldap.OPT_REFERRALS, 0)
				lauth.simple_bind_s( (dn), (password) )
			except ldap.LDAPError as e:
				# Password was wrong
				return False

			# Return that LDAP auth succeeded
			return True

	return False

################################################################################
		
def get_users_groups_from_ldap(username):
	"""Talks to LDAP and gets the list of the given users groups. This
	information is then stored in Redis so that it can be accessed 
	quickly."""


	# Connect to the LDAP server
	l = connect()

	# Now search for the user object
	try:
		results = l.search_s(app.config['LDAP_SEARCH_BASE'], ldap.SCOPE_SUBTREE, (app.config['LDAP_USER_ATTRIBUTE']) + "=" + username)
	except ldap.LDAPError as e:
		return None

	# Handle the search results
	for result in results:
		dn	= result[0]
		attrs	= result[1]

		if dn == None:
			return None
		else:
			# Found the DN. Yay! Now bind with that DN and the password the user supplied
			if 'memberOf' in attrs:
				if len(attrs['memberOf']) > 0:

					app.logger.debug("Found LDAP user groups for " + username)

					## Delete the existing cache
					curd = g.db.cursor(mysql.cursors.DictCursor)
					curd.execute('DELETE FROM `ldap_group_cache` WHERE `username` = %s', (username,))
					
					## Create the new cache
					groups = []
					for group in attrs['memberOf']:
						## We only want the group name, not the DN
						cn_regex = re.compile("^(cn|CN)=([^,;]+),")

						matched = cn_regex.match(group)
						if matched:
							group = matched.group(2)
						else:
							## didn't find the cn, so skip this 'group'
							continue

						curd.execute('INSERT INTO `ldap_group_cache` (`username`, `group`) VALUES (%s,%s)', (username,group.lower(),))
						groups.append(group)

					## Set the cache expiration
					curd.execute('REPLACE INTO `ldap_group_cache_expire` (`username`, `expiry_date`) VALUES (%s,NOW() + INTERVAL 15 MINUTE)', (username,))

					## Commit the transaction
					g.db.commit()

					return groups
				else:
					return None
			else:
				return None

	return None
