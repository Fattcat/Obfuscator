import ast
import builtins
import random
import string
import sys

BUILTINS = set(dir(builtins))
XOR_KEY = random.randint(1, 255)

def rand_name(n=32):
    return ''.join(random.choice(string.ascii_letters) for _ in range(n))

def xor_encode(s):
    return [ord(c) ^ XOR_KEY for c in s]


class Obfuscator(ast.NodeTransformer):
    def __init__(self):
        self.map = {}
        self.decode_fn = rand_name()
        self.protected = {self.decode_fn}

    # ---------- helpers ----------
    def rename(self, name):
        if (
            name in BUILTINS or
            name.startswith("__") or
            name in self.protected
        ):
            return name

        if name not in self.map:
            self.map[name] = rand_name()

        return self.map[name]

    def decode_call(self, s):
        return ast.Call(
            func=ast.Name(self.decode_fn, ast.Load()),
            args=[
                ast.List(
                    elts=[ast.Constant(x) for x in xor_encode(s)],
                    ctx=ast.Load()
                )
            ],
            keywords=[]
        )

    # ---------- strings ----------
    def visit_Constant(self, node):
        if isinstance(node.value, str):
            return ast.copy_location(self.decode_call(node.value), node)
        return node

    # ---------- names ----------
    def visit_Name(self, node):
        return ast.copy_location(
            ast.Name(self.rename(node.id), node.ctx),
            node
        )

    # ---------- attributes ----------
    def visit_Attribute(self, node):
        node.value = self.visit(node.value)
        return node

    # ---------- functions ----------
    def visit_FunctionDef(self, node):
        self.protected.add(node.name)
        node.name = self.rename(node.name)
        self.generic_visit(node)
        return node

    def visit_AsyncFunctionDef(self, node):
        self.protected.add(node.name)
        node.name = self.rename(node.name)
        self.generic_visit(node)
        return node

    # ---------- arguments ----------
    def visit_arg(self, node):
        node.arg = self.rename(node.arg)
        return node

    # ---------- class ----------
    def visit_ClassDef(self, node):
        self.protected.add(node.name)
        node.name = self.rename(node.name)
        self.generic_visit(node)
        return node

    # ---------- imports ----------
    def visit_Import(self, node):
        for a in node.names:
            if a.asname:
                a.asname = self.rename(a.asname)
            else:
                self.protected.add(a.name.split(".")[0])
        return node

    def visit_ImportFrom(self, node):
        for a in node.names:
            if a.asname:
                a.asname = self.rename(a.asname)
            else:
                self.protected.add(a.name)
        return node

    # ---------- except ----------
    def visit_ExceptHandler(self, node):
        if node.name:
            self.protected.add(node.name)
        self.generic_visit(node)
        return node

    # ---------- f-strings ----------
    def visit_JoinedStr(self, node):
        parts = []

        for v in node.values:
            if isinstance(v, ast.Constant) and isinstance(v.value, str):
                parts.append(self.decode_call(v.value))
            elif isinstance(v, ast.FormattedValue):
                parts.append(
                    ast.Call(
                        func=ast.Name("str", ast.Load()),
                        args=[self.visit(v.value)],
                        keywords=[]
                    )
                )

        if not parts:
            return ast.Constant("")

        expr = parts[0]
        for p in parts[1:]:
            expr = ast.BinOp(expr, ast.Add(), p)

        return expr


def main(inp, outp):
    with open(inp, "r", encoding="utf-8") as f:
        src = f.read()

    tree = ast.parse(src)

    obf = Obfuscator()
    tree = obf.visit(tree)
    ast.fix_missing_locations(tree)

    runtime = f"""
def {obf.decode_fn}(x):
    return ''.join(chr(i ^ {XOR_KEY}) for i in x)
"""

    with open(outp, "w", encoding="utf-8") as f:
        f.write(runtime)
        f.write(ast.unparse(tree))


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python obfuscator.py in.py out.py")
        sys.exit(1)

    main(sys.argv[1], sys.argv[2])
