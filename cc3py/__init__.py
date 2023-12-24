from importer import importer
importer("../../pyltr/pyltr", __file__)
importer("../../pycdb/pycdb", __file__)

from pycdb import test_identifier

def ppush(j, s):
	if j[0] == "let":
		j[2].append(s)
		return j
	return ["let", [], [j, s]]
def pprep(j, s):
	if j[0] == "let":
		j[2] = [s] + j[2]
		return j
	return ["let", [], [s, j]]

class Translator:
	def __init__(self):
		self.label = 0
		# Scope label stack
		# each member is [begin, after]
		# true means used
		self.sls = []
		self.exitlabel = False
	def dparams(self, j):
		result = []
		for [x, ptype, dbody] in j:
			assert x == "declare"
			ty, name = self.declare(ptype, dbody)
			result.append([ty, name])
		return result
	def declare(self, ptype, dbody):
		if isinstance(dbody, str):
			return (dbody, ptype)
		if dbody == []:
			return (None, ptype)
		name, ty = self.declare(ptype, dbody[1])
		match dbody[0]:
			case "arg":
				params = self.dparams(dbody[2])
				v = ["arg", ty, params]
			case "array":
				v = ["array", ty, dbody[2]]
			case "ptr":
				# TODO: properly tests compound types
				if isinstance(ty, list) and ty[0] == "arg":
					_, ret, arg = ty
					v = ["arg", ["ptr", ret], arg]
				else:
					v = ["ptr", ty]
			case x:
				raise Exception(x)
		return (name, v)
	def cexpr(self, j):
		if isinstance(j, str):
			return j
		j1 = []
		j1.append(self.cexpr(j[0]))
		match j1[0]:
			case "cast":
				# primitive type like int will be (int, [])
				assert len(j[2]) == 3
				assert j[2][0] == "type"
				name, ty = self.declare(j[2][1], j[2][2])
				assert name == None
				return ["cast", ty, self.cexpr(j[1])]
		for jj in j[1:]:
			j1.append(self.cexpr(jj))
		return j1
	def stmtexpr(self, j):
		assert j[0] == "stmtexpr"
		if j[1] == []:
			return ["nop"]
		j = j[1]
		if len(j) == 1 and test_identifier(j[0]):
			return ["nop"]
		if isinstance(j[0], str) and not test_identifier(j[0]):
			# op1 op2
			j2 = [j[0]]
			for jj in j[1:]:
				jj = self.cexpr(jj)
				j2.append(jj)
			return j2
		assert j[0] == "apply"
		assert len(j) == 3
		assert isinstance(j[2], list)
		func = self.cexpr(j[1])
		args = [self.cexpr(jj) for jj in j[2]]
		return ["apply", func, args]
	def control_for(self, j):
		assert len(j) == 3
		assert len(j[1]) == 3
		self.sls.append([None, None])
		proc = []
		decls = []
		init = j[1][0]
		if init[0] == "stmtexpr":
			proc.append(self.stmtexpr(init))
		else:
			assert init[0] == "stmtdec"
			self.stmtdec(init, decls, proc)
		body = self.procedure(j[2])
		if self.sls[-1][0] != None:
			l = ["label", self.sls[-1][0]]
			body = ppush(body, l)
		body = ppush(body, self.stmtexpr(j[1][2]))
		condition = self.stmtexpr(j[1][1])
		if condition == ["nop"]:
			condition = ["lit", "int", "1"]
		whl = ["while", condition, body]
		proc.append(whl)
		if self.sls[-1][1] != None:
			l = ["label", self.sls[-1][1]]
			proc.append(l)
		return ["let", decls, proc]
	def lbl(self, name):
		self.label += 1
		return f"{name}{self.label - 1}"
	def control_ifcont(self, j, lbl):
		if j[0] == "else":
			return [self.procedure(j[1])]
		assert j[0] == "elif"
		j = j[1]
		s = ["if", self.cexpr(j[1]), self.procedure(j[2])]
		if len(j[3]) == 0:
			return [s]
		s[2] = ppush(s[2], ["goto", lbl])
		result = [s]
		result += self.control_ifcont(j[3], lbl)
		return result
	def control_if(self, j):
		assert len(j) == 4
		s = ["if", self.cexpr(j[1]), self.procedure(j[2])]
		if len(j[3]) == 0:
			return [s]
		lbl = self.lbl("ENDIF")
		s[2] = ppush(s[2], ["goto", lbl])
		result = [s]
		result += self.control_ifcont(j[3], lbl)
		result.append(["label", lbl])
		return result
	def control_while(self, j):
		assert len(j) == 3
		self.sls.append([None, None])
		x = ["while", self.cexpr(j[1]), self.procedure(j[2])]
		if self.sls[-1][0] != None:
			x[2] = pprep(x[2], ["label", self.sls[-1][0]])
		if self.sls[-1][1] != None:
			x = ppush(x, ["label", self.sls[-1][1]])
		self.sls.pop()
		return x
	def control_return(self, j):
		if len(j) == 1:
			self.exitlabel = True
			return ["goto", f"LEXIT"]
		assert len(j) == 2
		result = ["return"]
		result.append(self.cexpr(j[1]))
		return result
	def statement2(self, j):
		# control, call, expr
		if isinstance(j, str):
			return j
		assert isinstance(j, list)
		if j[0] == "for":
			return self.control_for(j)
		elif j[0] == "if":
			s = self.control_if(j)
			if s[0] != "if":
				assert isinstance(s[0], list)
				return ["let", [], s]
			return s
		elif j[0] == "while":
			return self.control_while(j)
		elif j[0] == "return":
			return self.control_return(j)
		elif j[0] in ["continue", "break"]:
			assert len(self.sls) > 0
			if j[0] == "continue":
				if self.sls[-1][0] == None:
					self.sls[-1][0] = self.lbl("CONT")
				lbl = self.sls[-1][0]
			else:
				if self.sls[-1][1] == None:
					self.sls[-1][1] = self.lbl("BREAK")
				lbl = self.sls[-1][1]
			return ["goto", lbl]
			raise Exception(j)
		elif j[0] == "begin":
			return self.procedure(j)
		return self.stmtexpr(j)
	def statement(self, j):
		assert isinstance(j, list)
		if j[0][0] == "stmtdec":
			return (None, j)
		s = self.statement2(j[0])
		return (s, j[1:])
	def sinit(self, name, term, idx):
		s = self.cexpr(term[1])
		if len(term) == 1:
			["=", ["@", name, idx], s]
			# array
		assert len(term) == 2
		return ["=", [".", name, term[0]], s]
	# decls: int x; pending x=1, modify those arrays
	def stmtdec(self, j, decls, pending):
		assert j[0] == "stmtdec"
		ty = j[1]
		bodys = j[2]
		for body in bodys:
			if isinstance(body, list):
				name, ty = self.declare(ty, body[1])
				val = body[2]
				if val[0] == "braceinit":
					for idx, term in enumerate(val[1]):
						s = self.sinit(name, term, idx)
						pending.append(s)
				else:
					pending.append(
						["=", name, self.cexpr(val)])
			else:
				name, ty = self.declare(ty, body)
			decls.append([name, ty])
	def procedure(self, block):
		if block[0] != "begin":
			return self.statement([block])[0]
		decls = []
		idx = 1
		# translate header
		pending = []
		while idx < len(block):
			if block[idx][0] != "stmtdec":
				break
			self.stmtdec(block[idx], decls, pending)
			idx += 1
		block = block[idx:]
		result = ["let", decls, pending]
		# translate body
		if len(block) == 0:
			return result
		while block:
			j, block = self.statement(block)
			if j == None: # meet next stmtdec
				result[2].append(
					self.procedure(["begin"] + block))
				break
			if j[0] == "let" and j[1] == []:
				result[2] += j[2]
			else:
				result[2].append(j)
		return result
	def ast2c3(self, block):
		match block[0]:
			case "static" | "defun":
				assert block[1] == "declare"
				name, ty = self.declare(block[2], block[3])
				assert ty[0] == "arg"
				body = self.procedure(block[4])
				if self.exitlabel:
					body = ppush(body, ["label", "LEXIT"])
				return ["fn", name, ty[2], ty[1], body]
			case "decfun":
				assert block[1] == "declare"
				name, ty = self.declare(block[2], block[3])
				assert ty[0] == "arg"
				return ["fn", name, ty[2], ty[1],
					["let", [], []]]
			case "typedef_su":
				decls = []
				for lit, ptype, name in block[2]:
					assert lit == "declare"
					name, ty = self.declare(ptype, name)
					decls.append([name, ty])
				return [block[1], block[3], decls]
			case x:
				raise Exception(x)
