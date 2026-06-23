import ast
import os
import glob

tests_dir = "_sys/tests/unit"
files = glob.glob(f"{tests_dir}/*.py")

class Visitor(ast.NodeVisitor):
    def __init__(self, filename):
        self.filename = filename

    def visit_Call(self, node):
        if isinstance(node.func, ast.Attribute):
            if node.func.attr in ('write_text', 'write_bytes'):
                print(f"{self.filename}:{node.lineno} - {node.func.attr}")
        elif isinstance(node.func, ast.Name):
            if node.func.id == 'open':
                print(f"{self.filename}:{node.lineno} - open")
        self.generic_visit(node)

for f in files:
    with open(f, "r", encoding="utf-8") as file:
        tree = ast.parse(file.read(), filename=f)
        Visitor(f).visit(tree)
