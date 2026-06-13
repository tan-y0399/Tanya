"""自定义工具文件：语法诊断 + 沙箱试运行"""
from __future__ import annotations

import ast
import json
import re
from typing import Any, Callable, Dict, List, Tuple

ALLOWED_EXTENSIONS = {".py", ".json"}

FORBIDDEN_CODE_PATTERNS: List[Tuple[str, str]] = [
    (r"\bos\.system\b", "禁止使用 os.system"),
    (r"\bsubprocess\b", "禁止使用 subprocess"),
    (r"\beval\s*\(", "禁止使用 eval"),
    (r"\bexec\s*\(", "禁止使用 exec（工具文件内 run 函数除外）"),
    (r"__import__\s*\(", "禁止使用 __import__"),
    (r"\bopen\s*\(", "禁止使用 open 读写文件"),
    (r"\bshutil\b", "禁止使用 shutil"),
    (r"\bsocket\b", "禁止使用 socket"),
]

SAFE_BUILTINS = {
    "True": True,
    "False": False,
    "None": None,
    "str": str,
    "int": int,
    "float": float,
    "bool": bool,
    "list": list,
    "dict": dict,
    "tuple": tuple,
    "set": set,
    "len": len,
    "min": min,
    "max": max,
    "sum": sum,
    "round": round,
    "sorted": sorted,
    "range": range,
    "enumerate": enumerate,
    "isinstance": isinstance,
    "print": print,
}


def name_from_filename(filename: str) -> str:
    base = (filename or "custom_tool").rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    if "." in base:
        base = base.rsplit(".", 1)[0]
    name = re.sub(r"[^a-zA-Z0-9_]", "_", base)
    name = re.sub(r"_+", "_", name).strip("_").lower()
    if not name:
        name = "custom_tool"
    if name[0].isdigit():
        name = f"tool_{name}"
    return name[:100]


def _scan_dangerous_code(source: str) -> List[str]:
    errors: List[str] = []
    cleaned = re.sub(r"def run\s*\(", "def run(", source)
    for pattern, msg in FORBIDDEN_CODE_PATTERNS:
        if pattern == r"\bexec\s*\(" and "def run" in source:
            if re.search(r"(?<![\w])exec\s*\(", source):
                errors.append(msg)
        elif re.search(pattern, source):
            errors.append(msg)
    return errors


def _normalize_meta(
    default_name: str,
    raw: Dict[str, Any],
) -> Tuple[str, str, str, int, Dict[str, Any], Dict[str, Any]]:
    name = (raw.get("name") or default_name).strip()
    description = (raw.get("description") or "").strip()
    category = (raw.get("category") or "system_operation").strip()
    risk_level = int(raw.get("riskLevel") or raw.get("risk_level") or 1)
    config = raw.get("config") or {}
    trial_args = raw.get("trialArgs") or raw.get("trial_args") or {}
    if not isinstance(config, dict):
        config = {}
    if not isinstance(trial_args, dict):
        trial_args = {}
    return name, description, category, risk_level, config, trial_args


def _trial_run(run_fn: Callable[..., Any], trial_args: Dict[str, Any]) -> Dict[str, Any]:
    try:
        result = run_fn(**trial_args)
    except Exception as exc:
        return {"ok": False, "error": f"试运行异常: {exc}"}

    if not isinstance(result, dict):
        return {"ok": False, "error": "run() 必须返回 dict"}
    if not result.get("success"):
        return {"ok": False, "error": result.get("error") or "试运行返回 success=false"}
    return {"ok": True, "result": result}


def _load_python_run(source: str) -> Tuple[Dict[str, Any], Callable[..., Any] | None, List[str]]:
    errors: List[str] = []
    try:
        ast.parse(source)
    except SyntaxError as exc:
        return {}, None, [f"Python 语法错误: {exc}"]

    errors.extend(_scan_dangerous_code(source))
    if errors:
        return {}, None, errors

    namespace: Dict[str, Any] = {"__builtins__": SAFE_BUILTINS}
    try:
        # globals 与 locals 必须为同一 dict，否则 run() 内无法解析模块级辅助函数
        exec(source, namespace, namespace)
    except Exception as exc:
        return namespace, None, [f"代码加载失败: {exc}"]

    run_fn = namespace.get("run")
    if not callable(run_fn):
        return namespace, None, ["缺少可调用函数 run(**kwargs)"]

    return namespace, run_fn, []


def validate_tool_file(filename: str, content: str) -> Dict[str, Any]:
    """诊断并试运行工具文件，返回结构化结果供前端展示。"""
    filename = (filename or "").strip()
    content = content or ""
    default_name = name_from_filename(filename)

    if not content.strip():
        return _fail("diagnose", "文件内容为空", default_name)

    ext = ""
    if "." in filename:
        ext = "." + filename.rsplit(".", 1)[-1].lower()

    if ext not in ALLOWED_EXTENSIONS:
        return _fail(
            "diagnose",
            f"不支持的文件类型，请上传 {', '.join(sorted(ALLOWED_EXTENSIONS))}",
            default_name,
        )

    if ext == ".json":
        return _validate_json(default_name, content)
    return _validate_python(default_name, content)


def _validate_json(default_name: str, content: str) -> Dict[str, Any]:
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        return _fail("diagnose", f"JSON 解析失败: {exc}", default_name)

    if not isinstance(data, dict):
        return _fail("diagnose", "JSON 根节点必须是对象", default_name)

    name, description, category, risk_level, config, trial_args = _normalize_meta(default_name, data)
    diagnose_msgs = ["JSON 结构校验通过"]

    if not description:
        return _fail("diagnose", "缺少 description 字段", name, diagnose_msgs)

    python_source = data.get("python") or data.get("source") or ""
    if python_source:
        namespace, run_fn, errors = _load_python_run(str(python_source))
        if errors:
            return _fail("diagnose", errors[0], name, diagnose_msgs, extra_errors=errors[1:])
        assert run_fn is not None
        trial = _trial_run(run_fn, trial_args)
        if not trial["ok"]:
            return {
                "ok": False,
                "stage": "trial",
                "name": name,
                "description": description,
                "category": category,
                "riskLevel": risk_level,
                "config": {**config, "sourceType": "json+python", "sourceContent": content},
                "diagnose": {"ok": True, "messages": diagnose_msgs + ["内嵌 Python 代码诊断通过"]},
                "trial": trial,
            }
        diagnose_msgs.append("内嵌 Python 试运行通过")
        return _success(
            name,
            description,
            category,
            risk_level,
            {**config, "sourceType": "json+python", "sourceContent": content},
            diagnose_msgs,
            trial,
        )

    diagnose_msgs.append("元数据工具定义有效（无代码段，跳过代码试运行）")
    return _success(
        name,
        description,
        category,
        risk_level,
        {**config, "sourceType": "json", "sourceContent": content},
        diagnose_msgs,
        {"ok": True, "result": {"success": True, "data": {"mode": "metadata_only"}}},
    )


def _validate_python(default_name: str, content: str) -> Dict[str, Any]:
    namespace, run_fn, errors = _load_python_run(content)
    if errors:
        return _fail("diagnose", errors[0], default_name, extra_errors=errors[1:])

    assert run_fn is not None
    meta_name = str(namespace.get("NAME") or default_name).strip() or default_name
    description = str(namespace.get("DESCRIPTION") or "").strip()
    category = str(namespace.get("CATEGORY") or "system_operation").strip()
    risk_level = int(namespace.get("RISK_LEVEL") or 1)
    config = namespace.get("CONFIG") if isinstance(namespace.get("CONFIG"), dict) else {}
    trial_args = namespace.get("TRIAL_ARGS") if isinstance(namespace.get("TRIAL_ARGS"), dict) else {}

    diagnose_msgs = ["Python 语法诊断通过", "安全规则扫描通过"]

    if not description:
        return _fail("diagnose", "缺少 DESCRIPTION 变量", meta_name, diagnose_msgs)

    trial = _trial_run(run_fn, trial_args)
    if not trial["ok"]:
        return {
            "ok": False,
            "stage": "trial",
            "name": meta_name,
            "description": description,
            "category": category,
            "riskLevel": risk_level,
            "config": {**config, "sourceType": "python", "sourceContent": content},
            "diagnose": {"ok": True, "messages": diagnose_msgs},
            "trial": trial,
        }

    diagnose_msgs.append("run(**kwargs) 试运行通过")
    return _success(
        meta_name,
        description,
        category,
        risk_level,
        {**config, "sourceType": "python", "sourceContent": content},
        diagnose_msgs,
        trial,
    )


def _fail(
    stage: str,
    message: str,
    name: str,
    diagnose_msgs: List[str] | None = None,
    extra_errors: List[str] | None = None,
) -> Dict[str, Any]:
    errors = [message] + (extra_errors or [])
    return {
        "ok": False,
        "stage": stage,
        "name": name,
        "diagnose": {
            "ok": stage != "diagnose" or False,
            "messages": diagnose_msgs or [],
            "errors": errors,
        },
        "trial": {"ok": False, "error": message if stage == "trial" else ""},
    }


def _success(
    name: str,
    description: str,
    category: str,
    risk_level: int,
    config: Dict[str, Any],
    diagnose_msgs: List[str],
    trial: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "ok": True,
        "stage": "done",
        "name": name,
        "description": description,
        "category": category,
        "riskLevel": max(1, min(5, risk_level)),
        "config": config,
        "diagnose": {"ok": True, "messages": diagnose_msgs, "errors": []},
        "trial": trial,
    }
