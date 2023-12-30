from importer import importer
importer("../../pyltr/pyltr", __file__)
importer("../../pycdb/pycdb", __file__)

from pycdb import test_identifier, opprec
from pyltr import S

def dparams(j):
	result = []
	for [x, ptype, dbody] in j:
		assert x == "declare"
		name, ty = declare(ptype, dbody)
		if name == None:
			result.append(ty)
		else:
			result.append([name, ty])
	if result == [["void"]]:
		return []
	return result
def declare(ptype, dbody):
	l = []
	while isinstance(dbody, list):
		if dbody == []:
			break
		l.append(dbody)
		dbody = dbody[1]
	if isinstance(dbody, str):
		name = dbody
	else:
		assert dbody == []
		name = None
	v = ptype
	for ll in l:
		match ll[0]:
			case "Arg":
				params = dparams(ll[2])
				if params == ["void"]:
					params = []
				v = ["Arg", v] + params
			case "Array":
				v = ["Array", v, cexpr(ll[2])]
			case "Ptr":
				v = ["Ptr", v]
			case x:
				raise Exception(x)
	return (name, v)
def initval(j):
	if isinstance(j, list):
		if j[0] == "sval":
			return sval(j)
		elif j[0] == "aval":
			return aval(j)
	return cexpr(j)
def sval(j):
	for idx, jj in enumerate(j):
		if idx == 0:
			assert jj == "sval"
			continue
		j[idx][1] = initval(jj[1])
	return j
def aval(j):
	for idx, jj in enumerate(j):
		if idx == 0:
			assert jj == "aval"
			continue
		j[idx] = initval(jj)
	return j
def cexpr(j):
	if isinstance(j, str):
		return j
	match j[0]:
		case "cast" | "casts":
			assert len(j[1]) == 3
			assert j[1][0] == "declare"
			name, ty = declare(j[1][1], j[1][2])
			assert name == None
			return ["cast", ty, initval(j[2])]
		case "sizeof":
			assert len(j[1]) == 3
			assert j[1][0] == "declare"
			name, ty = declare(j[1][1], j[1][2])
			assert name == None
			return ["sizeof", ty]
		case "lit":
			match j[1]:
				case "str":
					return S('"' + j[2] + '"')
				case "char":
					return S("'" + j[2] + "'")
				case x:
					return S(j[2])
		case "type":
			name, ty = declare(j[1], j[2])
			assert name == None
			return ty
	if j[0] == "apply":
		return apply(j)
	assert(isinstance(opprec(j[0]), int))
	for idx, jj in enumerate(j[1:]):
		j[idx + 1] = cexpr(jj)
	return j
def apply(j):
	assert j[0] == "apply"
	assert len(j) == 3
	assert isinstance(j[2], list)
	func = [cexpr(j[1])]
	args = [cexpr(jj) for jj in j[2]]
	return func + args
def control_ifcont(j):
	if j[0] == "else":
		return [control_branch("true", j[1])]
	assert j[0] == "elif"
	j = j[1]
	branch = [control_branch(j[1], j[2])]
	if len(j[3]) == 0:
		return branch
	branch += control_ifcont(j[3])
	return branch
def control_branch(cond, body):
	return [cexpr(cond), procedure(body)]
def control_case(j):
	raise Exception("switch is unsupported")
	result = ["case", cexpr(j[1])]
	for jj in j[2:]:
		result += [control_branch(*jj)]
	return result
def control_if(j):
	assert len(j) == 4
	branches = [control_branch(j[1], j[2])]
	if len(j[3]) > 0:
		branches += control_ifcont(j[3])
	return ["cond"] + branches
def control_while(j):
	assert len(j) == 3
	x = ["while", cexpr(j[1]), procedure(j[2])]
	return x
def control_return(j):
	if len(j) == 1:
		exitlabel = True
		return ["goto", f"LEXIT"]
	assert len(j) == 2
	result = ["return"]
	result.append(cexpr(j[1]))
	return result
def statement(j):
	if isinstance(j, list) and len(j) == 0:
		return [["nop"]]
	if isinstance(j, list) and j[0] == "stmtdec":
		return stmtdec(j)
	else:
		return [statement2(j)]
def stmts2stmt(j):
	if len(j) == 1:
		return j[0]
	else:
		return ["begin"] + j
def for23stmt(j):
	j = statement(j)
	assert len(j) == 1
	j = j[0]
	if j == []:
		return ["nop"]
	return j
def statement2(j):
	# control, call, expr
	if isinstance(j, str):
		return j
	assert isinstance(j, list)
	if j[0] == "for":
		assert len(j[1]) == 3
		c1 = stmts2stmt(statement(j[1][0]))
		c2 = for23stmt(j[1][1])
		c3 = for23stmt(j[1][2])
		return ["for", c1, c2, c3, procedure(j[2])]
	elif j[0] == "case":
		return control_case(j)
	elif j[0] == "if":
		return control_if(j)
	elif j[0] == "while":
		return control_while(j)
	elif j[0] == "return":
		return control_return(j)
	elif j[0] == "returnvoid":
		return ["returnvoid"]
	elif j[0] in ["continue", "break"]:
		assert len(j) == 1
		return j
	elif j[0] == "begin":
		return procedure(j)
	elif j[0] == "expr":
		return cexpr(j[1])
	else:
		raise Exception(j)
def sinit(name, term, idx):
	s = cexpr(term[1])
	if len(term) == 1:
		["=", ["@", name, idx], s]
		# array
	assert len(term) == 2
	return ["=", [".", name, term[0]], s]
def stmtdec_body(j, ty, body):
	name, ty = declare(ty, body[1])
	match body[0]:
		case "set" | "sets":
			val = initval(body[2])
			return ["set", name, ty, val]
		case "var":
			return ["var", name, ty]
		case x:
			raise Exception(x)
def stmtdec(j):
	ty = j[1]
	bodys = j[2]
	result = []
	for body in bodys:
		result.append(stmtdec_body(j, ty, body))
	return result
def procedure(block):
	if block[0] != "begin":
		return stmts2stmt(statement(block))
	result = []
	for stmt in block[1:]:
		result += statement(stmt)
	return ["begin"] + result
def ast2c3(block):
	match block[0]:
		case "static" | "defun":
			assert block[1] == "declare"
			name, ty = declare(block[2], block[3])
			assert ty[0] == "Arg"
			body = procedure(block[4])
			return ["fn", name, ty[2:], ty[1], body]
		case "const":
			return ["const", block[2], block[1], cexpr(block[3])]
		case "decfun":
			assert block[1] == "declare"
			name, ty = declare(block[2], block[3])
			assert ty[0] == "Arg"
			return ["decfun", name, ty[2:], ty[1], []]
		case "typedef_su":
			decls = []
			for lit, ptype, name in block[2]:
				assert lit == "declare"
				name, ty = declare(ptype, name)
				decls.append([name, ty])
			return [block[1], block[3], decls]
		case x:
			raise Exception(x)
