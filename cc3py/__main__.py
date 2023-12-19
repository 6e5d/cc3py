import sys, json
from . import cc3c
from pyltr import dump

s = sys.stdin.read()
s = cc3c(s)
print(dump(s))
