import re

expr = "b = 2 + a*10"

pattern = re.compile(r"\s*(?:(\d+)|(\w+)|(.))")

scan = pattern.scanner(expr)

while 1:
    m = scan.match()
    if not m:
        break
    print(m.groups(),m.lastindex, repr(m.group(m.lastindex)))