#!/usr/bin/env python3
import ast
import re
import sys
from pathlib import Path

snake_case_pattern = re.compile(r"^[a-z_][a-z0-9_]*$")

def is_snake_case(name: str) -> bool:
    return bool(snake_case_pattern.match(name))

class CodeReviewer(ast.NodeVisitor):
    def __init__(self, code: str):
        self.code = code
        self.issues = []
        self.tree = ast.parse(code)

    def check_function_names(self):
        for node in ast.walk(self.tree):
            if isinstance(node, ast.FunctionDef):
                if not is_snake_case(node.name):
                    self.issues.append(f"Function name `{node.name}` must be lower_snake_case.")

    def check_variable_names(self):
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        if not is_snake_case(target.id):
                            self.issues.append(f"Variable name `{target.id}` must be lower_snake_case.")

    def check_endpoint_rules(self):
        for node in ast.walk(self.tree):
            if isinstance(node, ast.FunctionDef):
                has_route = any(
                    isinstance(dec, ast.Call)
                    and hasattr(dec.func, "attr")
                    and dec.func.attr == "route"
                    for dec in node.decorator_list
                )
                if has_route:
                    has_try = any(isinstance(n, ast.Try) for n in ast.walk(node))
                    if not has_try:
                        self.issues.append(f"Endpoint `{node.name}` missing try/except block.")
                    has_json_return = any(
                        isinstance(n, ast.Call)
                        and hasattr(n.func, "id")
                        and n.func.id in ["json", "jsonify"]
                        for n in ast.walk(node)
                    )
                    if not has_json_return:
                        self.issues.append(f"Endpoint `{node.name}` must return a JSON response.")
                    first_stmt = node.body[0] if node.body else None
                    if first_stmt and not isinstance(first_stmt, ast.If):
                        self.issues.append(f"Endpoint `{node.name}` must have a validation check at the top.")

    def check_db_session_rules(self):
        code_lines = self.code.splitlines()
        for node in ast.walk(self.tree):
            if isinstance(node, ast.FunctionDef):
                func_code = "\n".join(code_lines[node.lineno - 1 : node.end_lineno])
                if "getDbSession" in func_code or "create_dbsession_pg" in func_code:
                    if "finally" not in func_code or ".close()" not in func_code:
                        self.issues.append(f"Function `{node.name}` must close DB sessions in a finally block.")
                    if any(keyword in func_code for keyword in ["add", "update", "insert"]):
                        if "except" not in func_code or ".rollback()" not in func_code:
                            self.issues.append(f"Function `{node.name}` does DB writes but is missing rollback in except block.")

    def run_checks(self):
        self.check_function_names()
        self.check_variable_names()
        self.check_endpoint_rules()
        self.check_db_session_rules()
        return self.issues

def review_file(filepath: Path):
    code = filepath.read_text()
    reviewer = CodeReviewer(code)
    issues = reviewer.run_checks()
    if issues:
        print(f"Issues found in {filepath}:")
        for issue in issues:
            print("  " + issue)
        return False
    else:
        print(f"{filepath} passed all checks.")
        return True

def main():
    if len(sys.argv) < 2:
        print("Usage: python code_reviewer.py <file1.py> [<file2.py> ...]")
        sys.exit(1)
    all_passed = True
    for file_arg in sys.argv[1:]:
        path = Path(file_arg)
        if not review_file(path):
            all_passed = False
    if not all_passed:
        sys.exit(1)

if __name__ == "__main__":
    main()
