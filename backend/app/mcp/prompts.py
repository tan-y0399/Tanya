from __future__ import annotations

from typing import Any, Dict, List

PROMPTS: List[Dict[str, Any]] = [
    {
        "name": "incident_analysis",
        "description": "Analyze incident with logs, metrics, and probable root causes",
        "arguments": [
            {"name": "target", "required": True, "description": "Service, host, or issue target"},
            {"name": "symptoms", "required": False, "description": "Observed symptoms"},
        ],
    },
    {
        "name": "log_triage",
        "description": "Triage recent logs and identify abnormal patterns",
        "arguments": [
            {"name": "service", "required": False, "description": "Service name"},
            {"name": "lines", "required": False, "description": "Number of lines to inspect"},
        ],
    },
    {
        "name": "risk_review",
        "description": "Evaluate command or change request risk level before execution",
        "arguments": [
            {"name": "action", "required": True, "description": "Proposed command or operation"},
        ],
    },
]


def list_prompts() -> List[Dict[str, Any]]:
    return PROMPTS


def get_prompt_definition(name: str) -> Dict[str, Any] | None:
    for prompt in PROMPTS:
        if prompt["name"] == name:
            return prompt
    return None


def get_prompt(name: str, arguments: Dict[str, Any] | None = None) -> Dict[str, Any]:
    arguments = arguments or {}
    if name == "incident_analysis":
        target = arguments.get("target", "unknown target")
        symptoms = arguments.get("symptoms", "")
        text = (
            f"Analyze the incident for {target}.\n"
            f"Symptoms: {symptoms or 'not provided'}.\n"
            "Collect logs, metrics, service status, likely root causes, and safe remediation steps."
        )
    elif name == "log_triage":
        service = arguments.get("service", "")
        lines = arguments.get("lines", 50)
        text = (
            f"Triage recent logs for service={service or 'all services'} with lines={lines}.\n"
            "Summarize abnormalities, errors, and next checks."
        )
    elif name == "risk_review":
        action = arguments.get("action", "")
        text = (
            f"Review the following action for operational risk and safety controls:\n{action}\n"
            "Return risk level, blocked patterns, and whether approval is required."
        )
    else:
        return {"success": False, "error": f"Unknown prompt: {name}"}
    return {"success": True, "data": {"name": name, "text": text}}
