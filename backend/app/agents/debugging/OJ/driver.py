import json
import ast
import re

# ============================================================
# 禁止學生 import 的模組
# ============================================================

FORBIDDEN_IMPORTS = {
    "os",
    "sys",
    "subprocess",
    "inspect",
    "builtins",
    "threading",
    "multiprocessing",
}


# ============================================================
# 檢查危險 import（使用 AST）
# ============================================================

def detect_forbidden_imports(user_code: str):
    """
    若學生程式碼含有禁止 import，回傳該模組名稱
    否則回傳 None
    """
    try:
        tree = ast.parse(user_code)
    except SyntaxError:
        return "SyntaxError"

    for node in ast.walk(tree):

        # case: import xxx
        if isinstance(node, ast.Import):
            for alias in node.names:
                module = alias.name.split(".")[0]
                if module in FORBIDDEN_IMPORTS:
                    return module

        # case: from xxx import yyy
        if isinstance(node, ast.ImportFrom):
            if node.module:
                module = node.module.split(".")[0]
                if module in FORBIDDEN_IMPORTS:
                    return module

    return None


# ============================================================
# 檢查是否有 input()
# ============================================================

def validate_stdio_code(user_code: str) -> bool:
    """STDIO 題型必須要有 input()"""
    patterns = [
        r"\binput\s*\(",
        r"sys\.stdin",
        r"sys\.stdin\.read"
    ]
    return any(re.search(p, user_code) for p in patterns)


# ============================================================
# 檢查是否定義指定 function
# ============================================================

def validate_function_code(user_code: str, entry_point: str) -> bool:
    pattern = rf"def\s+{entry_point}\s*\("
    return re.search(pattern, user_code) is not None


# ============================================================
# 建立注入執行碼（Driver Code）
# ============================================================

def build_driver_code(
    user_code: str,
    input_val,
    judge_type: str,
    entry_point: str
) -> str:
    # user_code = user_code.replace('\r\n', '\n').replace('\r', '\n')
    safe_input_json = json.dumps(input_val)

    # ============================================================
    # (1) Sandbox：檢查危險 import
    # ============================================================

    forbidden = detect_forbidden_imports(user_code)
    if forbidden:
        return f"""
raise RuntimeError("Forbidden import detected: {forbidden}")
"""

    # ============================================================
    # (2) FUNCTION 題型
    # ============================================================

    if judge_type == "function":

        # 必須定義該 function，否則直接 RE
        if not validate_function_code(user_code, entry_point):
            return f"""
raise RuntimeError("Function `{entry_point}` not found in submission")
"""
        final_code = f"""
import json

# --- User Code ---
{user_code}
# -----------------

_args = {safe_input_json}
if not isinstance(_args, list):
    _args = [_args]

try:
    result = {entry_point}(*_args)
except Exception as e:
    raise RuntimeError(str(e))

print(json.dumps(result))
"""
        return final_code

    # ============================================================
    # (3) STDIO 題型
    # ============================================================

    # STDIO 題型必須使用 input()
    if not validate_stdio_code(user_code):
        return """
raise RuntimeError("This problem requires input(), but no input() was found in your code")
"""

    # STDIO 注入 code
    return f"""
import sys, io, json

# --- Prepare input ---
_input_data = {safe_input_json}

if isinstance(_input_data, list):
    _lines = [str(x) for x in _input_data]
else:
    _lines = [str(_input_data)]

_input_iter = iter(_lines)

# override input()
def input(prompt=None):
    try:
        return next(_input_iter)
    except StopIteration:
        raise EOFError("No more input")

# also fill stdin for libraries reading sys.stdin
sys.stdin = io.StringIO("\\n".join(_lines))

# --- User Code ---
{user_code}
"""