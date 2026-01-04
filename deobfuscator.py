import ast
import sys

class DecodeInfo:
    def __init__(self):
        self.func_name = None
        self.xor_key = None


class Deobfuscator(ast.NodeTransformer):
    def __init__(self, decode_info: DecodeInfo):
        self.info = decode_info

    # ---------- replace decode_fn([...]) ----------
    def visit_Call(self, node):
        self.generic_visit(node)

        if (
            isinstance(node.func, ast.Name)
            and node.func.id == self.info.func_name
            and len(node.args) == 1
            and isinstance(node.args[0], ast.List)
        ):
            values = []
            for elt in node.args[0].elts:
                if not isinstance(elt, ast.Constant):
                    return node
                values.append(elt.value)

            decoded = "".join(chr(v ^ self.info.xor_key) for v in values)
            return ast.Constant(decoded)

        return node


# ---------- extract decode fn + XOR key ----------
def extract_decode_info(tree: ast.Module) -> DecodeInfo:
    info = DecodeInfo()

    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue

        # looking for: def X(data): k = N; return ''.join(chr(x ^ k) ...)
        assigns = [
            n for n in node.body
            if isinstance(n, ast.Assign)
        ]

        if not assigns:
            continue

        assign = assigns[0]
        if (
            isinstance(assign.targets[0], ast.Name)
            and assign.targets[0].id == "k"
            and isinstance(assign.value, ast.Constant)
        ):
            info.func_name = node.name
            info.xor_key = assign.value.value
            break

    if not info.func_name:
        raise RuntimeError("Decode function not found")

    return info


# ---------- remove runtime stub ----------
def remove_runtime(tree: ast.Module, decode_name: str):
    new_body = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == decode_name:
            continue
        new_body.append(node)
    tree.body = new_body


def main(inp, outp):
    with open(inp, encoding="utf-8") as f:
        src = f.read()

    tree = ast.parse(src)

    info = extract_decode_info(tree)

    tree = Deobfuscator(info).visit(tree)
    ast.fix_missing_locations(tree)

    remove_runtime(tree, info.func_name)

    with open(outp, "w", encoding="utf-8") as f:
        f.write(ast.unparse(tree))


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python deobfuscator.py obfuscated.py output.py")
        sys.exit(1)

    main(sys.argv[1], sys.argv[2])
