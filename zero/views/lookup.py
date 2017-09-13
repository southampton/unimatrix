#!/usr/bin/python

from zero import app
import zero.lib.user
from flask import render_template, g, jsonify, request, abort
import MySQLdb as mysql

@app.route('/lookup')
@zero.lib.user.login_required
def lookup():
	"""Renders the list of systems"""

	curd = g.db.cursor(mysql.cursors.DictCursor)
	curd.execute("""SELECT `name`, `package` FROM `systems` INNER JOIN `systems_packages` ON `sid`=`id`""")
	rows = curd.fetchall()

	return render_template('lookup/lookup.html',active="lookup",rows=rows)

@app.route('/lookup/json')
@zero.lib.user.login_required
def lookup_json():
	"""Renders the list of systems"""

	try:
		draw = int(request.args['draw'])
		start = int(request.args['start'])
		length = int(request.args['length'])
		
		search_system = str(request.args['columns[0][search][value]'])
		search_package = str(request.args['columns[1][search][value]'])
		order_on = int(request.args['order[0][column]'])
		order_dir = str(request.args['order[0][dir]'])
	except:
		abort(400)

	stmt = """ FROM `systems` INNER JOIN `systems_packages` ON `sid`=`id`"""

	cond = ''
	cond_params = ()
	if len(search_system) > 0 or len(search_package) > 0:
		cond = cond + ' WHERE '
		
		first = True
		if len(search_system) > 0:
			search_system = search_system.decode('string_escape')
			cond = cond + ' OR '.join(['`name` LIKE %s' for string in search_system.split('|')])
			for string in search_system.split('|'):
				cond_params = cond_params + ('%'+string+'%',) 
			first = False
		
		if len(search_package) > 0:
			if not first:
				cond = cond + ' AND'
			search_package = search_package.decode('string_escape')
			cond = cond + ' OR '.join(['`package` LIKE %s' for string in search_package.split('|')])
			for string in search_package.split('|'):
				cond_params = cond_params + ('%'+string+'%',) 

	if order_on == 0:
		sort = ' ORDER BY `name`'
	else:
		sort = ' ORDER BY `package`'
	if order_dir == 'desc':
		sort = sort + ' DESC'
	else:
		sort = sort + ' ASC'


	curd = g.db.cursor(mysql.cursors.DictCursor)

	data_stmt = 'SELECT `name`, `package`' + stmt + cond + sort + ' LIMIT %s, %s'
	curd.execute(data_stmt, cond_params + (start, length))
	data = curd.fetchall()

	filtered_stmt = 'SELECT COUNT(*) AS `filtered`' + stmt + cond
	curd.execute(filtered_stmt, cond_params)
	records_filtered = curd.fetchone()['filtered']
	
	total_stmt = 'SELECT COUNT(*) AS `total`' + stmt
	curd.execute(total_stmt)
	records_total = curd.fetchone()['total']

	return jsonify(draw=draw, recordsTotal=records_total, recordsFiltered=records_filtered, data=data)
