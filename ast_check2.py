import ast
import os
import glob

tests_dir = "_sys/tests/unit"
files = glob.glob(f"{tests_dir}/*.py")

class Visitor(ast.NodeVisitor):
    def __init__(self, filename):
        self.filename = filename

    def visit_Call(self, node):
        if isinstance(node.func, ast.Name) and node.func.id == 'Path':
            if getattr(node, 'args', None) and len(node.args) == 1:
                arg = node.args[0]
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    if '/' not in arg.value and '\\' not in arg.value and arg.value != ".":
                        print(f"{self.filename}:{node.lineno} - Path('{arg.value}')")
        self.generic_visit(node)

for f in files:
    with open(f, "r", encoding="utf-8") as file:
        tree = ast.parse(file.read(), filename=f)
        Visitor(f).visit(tree)
