from importer import importer
importer("../../pycparse/pycparse", __file__)
importer("../../pyltr/pyltr", __file__)
importer("../../pycdb/pycdb", __file__)

from pycdb import test_identifier
from pycparse.parse import parse_string
from pycparse import strip_preprocess

def dparams(j):
	result = []
	for [x, ptype, dbody] in j:
		assert x == "declare"
		ty, name = declare(ptype, dbody)
		result.append([ty, name])
	return result

def declare(ptype, dbody):
	if isinstance(dbody, str):
		return (ptype, dbody)
	if dbody == []:
		return (ptype, None)
	ty, name = declare(ptype, dbody[1])
	match dbody[0]:
		case "fn":
			params = dparams(dbody[2])
			return ([ty, params], name)
		case "array":
			return (["array", ty], name)
		case "ptr":
			return (["*", ty], name)
		case x:
			raise Exception(x)

def cexpr(j):
	if isinstance(j, str):
		return j
	j1 = []
	j1.append(cexpr(j[0]))
	match j1[0]:
		case "as":
			# even primitive type like int must be (int, [])
			assert len(j[2]) == 3
			assert j[2][0] == "type"
			ty, name = declare(j[2][1], j[2][2])
			assert name == None
			return ["as", cexpr(j[1]), ty]
	for jj in j[1:]:
		j1.append(cexpr(jj))
	return j1

def stmt_declare(ptype, stmt_dbody):
	if stmt_dbody[0] == "decinit":
		ty, name = declare(ptype, stmt_dbody[1])
		expr = cexpr(stmt_dbody[2])
		return [ty, name, expr]
	else:
		return list(declare(ptype, stmt_dbody))

# push a sentence to a procedure
def procedure_push(j, s):
	if j[0] == "begin":
		j[1].append(s)
		return j
	return ["begin", j, s]

def control_for(j):
	result = ["begin"]
	assert len(j[1]) == 3
	if len(j[1][0]) > 0:
		result.append(statement(j[1][0]))
	while_body = procedure(j[2])
	if len(j[1][2]) > 0:
		procedure_push(while_body, j[1][1])
	if len(j[1][1]) > 0:
		result.append(["while", j[1][1], while_body])
	else:
		result.append(["while", "1", while_body])
	return result

def control_ifwhile(j):
	assert len(j) == 3
	result = [j[0]]
	result.append(cexpr(j[1]))
	result.append(procedure(j[2]))
	return result

def control_return(j):
	assert len(j) == 2
	result = ["return"]
	result.append(cexpr(j[1]))
	return result

def statement(j):
	# declare, control, call
	if j[0] == "declare":
		s = [stmt_declare(j[1], jj) for jj in j[2]]
		if len(s) == 1:
			return s[0]
		else:
			return ["begin"] + s
	elif j[0] in ["for", "if", "while", "continue", "break", "return"]:
		if j[0] == "for":
			return control_for(j)
		elif j[0] in ["if", "while"]:
			return control_ifwhile(j)
		elif j[0] in ["return"]:
			return control_return(j)
		return j
	elif isinstance(j[0], str) and not test_identifier(j[0]):
		return j
	assert len(j) == 2
	assert isinstance(j[1], list)
	func = cexpr(j[0])
	args = [cexpr(jj) for jj in j[1]]
	return [func, args]

def procedure(block):
	if block[0] != "begin":
		return statement(block)
	else:
		return ["begin"] + [procedure(x) for x in block[1:]]

def ast2c3(block):
	match block[0]:
		case "static" | "defun":
			assert block[1] == "declare"
			ty, name = declare(block[2], block[3])
			body = procedure(block[4])
			return [ty[0], name, ty[1], body]
		case "typedef":
			ty, name = declare(block[1], block[2])
			return ["typedef", ty, name]
		case x:
			raise Exception(x)

def cc3c(s):
	j = parse_string(s, True)
	result = []
	for jj in j:
		result.append(ast2c3(jj))
	return result
