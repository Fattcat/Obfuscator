import ast
import random
import string
import sys
import builtins

XOR_KEY = random.randint(1, 255)
BUILTINS = set(dir(builtins))

def rand_name(n=24):
    return ''.join(random.choice(string.ascii_letters) for _ in range(n))

def xor_encode(s):
    return [ord(c) ^ XOR_KEY for c in s]

class Obfuscator(ast.NodeTransformer):
    def __init__(self):
        self.decode_fn = rand_name()
        self.import_fn = rand_name()
        self.name_map = {}
        self.protected = set()
        self.in_except = False

    # ---------- helpers ----------
    def map_name(self, name):
        if (
            name in BUILTINS or
            name.startswith("__") or
            name in self.protected
        ):
            return name

        if name not in self.name_map:
            self.name_map[name] = rand_name()

        return self.name_map[name]

    def decode_call(self, s):
        return ast.Call(
            func=ast.Name(self.decode_fn, ast.Load()),
            args=[ast.List([ast.Constant(x) for x in xor_encode(s)], ast.Load())],
            keywords=[]
        )

    # ---------- strings ----------
    def visit_Constant(self, node):
        if isinstance(node.value, str):
            return self.decode_call(node.value)
        return node

    # ---------- names ----------
    def visit_Name(self, node):
        return ast.Name(
            id=self.map_name(node.id),
            ctx=node.ctx
        )

    # ---------- function defs ----------
    def visit_FunctionDef(self, node):
        node.name = self.map_name(node.name)
        node.args = self.visit(node.args)
        node.body = [self.visit(x) for x in node.body]
        return node

    # ---------- arguments ----------
    def visit_arg(self, node):
        node.arg = self.map_name(node.arg)
        return node

    # ---------- EXCEPT HANDLER (CRITICAL FIX) ----------
    def visit_ExceptHandler(self, node):
        if node.name:
            self.protected.add(node.name)

        node.body = [self.visit(x) for x in node.body]
        return node

    # ---------- f-strings ----------
    def visit_JoinedStr(self, node):
        parts = []

        for v in node.values:
            if isinstance(v, ast.Constant):
                parts.append(self.decode_call(v.value))
            elif isinstance(v, ast.FormattedValue):
                parts.append(
                    ast.Call(
                        func=ast.Name("str", ast.Load()),
                        args=[self.visit(v.value)],
                        keywords=[]
                    )
                )

        expr = parts[0]
        for p in parts[1:]:
            expr = ast.BinOp(expr, ast.Add(), p)

        return expr

    # ---------- imports ----------
    def visit_Import(self, node):
        out = []
        for a in node.names:
            name = self.map_name(a.asname or a.name)
            out.append(
                ast.Assign(
                    targets=[ast.Name(name, ast.Store())],
                    value=ast.Call(
                        func=ast.Name(self.import_fn, ast.Load()),
                        args=[self.decode_call(a.name)],
                        keywords=[]
                    )
                )
            )
        return out

def main(inp, outp):
    src = open(inp, encoding="utf-8").read()
    tree = ast.parse(src)

    obf = Obfuscator()
    tree = obf.visit(tree)
    ast.fix_missing_locations(tree)

    runtime = f"""
def {obf.decode_fn}(data):
    k = {XOR_KEY}
    return ''.join(chr(x ^ k) for x in data)

def {obf.import_fn}(name):
    return __import__(name)
"""

    with open(outp, "w", encoding="utf-8") as f:
        f.write(runtime)
        f.write(ast.unparse(tree))

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python obfuscator.py in.py out.py")
        sys.exit(1)

    main(sys.argv[1], sys.argv[2])
