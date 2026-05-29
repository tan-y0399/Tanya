from __future__ import annotations

from typing import Dict, List

ROLE_TOOL_ALLOWLIST: Dict[str, List[str]] = {
    "admin": [
        "get_system_info",
        "get_cpu_info",
        "get_memory_info",
        "get_disk_info",
        "get_network_info",
        "get_network_connections",
        "get_network_interfaces",
        "get_process_list",
        "get_process_detail",
        "kill_process",
        "get_service_status",
        "manage_service",
        "get_file_list",
        "read_file",
        "get_logs",
        "get_users",
        "get_groups",
        "run_command",
    ],
    "auditor": [
        "get_system_info",
        "get_cpu_info",
        "get_memory_info",
        "get_disk_info",
        "get_network_info",
        "get_network_connections",
        "get_network_interfaces",
        "get_process_list",
        "get_process_detail",
        "get_service_status",
        "get_file_list",
        "read_file",
        "get_logs",
        "get_users",
        "get_groups",
    ],
    "deployer": [
        "get_system_info",
        "get_cpu_info",
        "get_memory_info",
        "get_disk_info",
        "get_network_info",
        "get_network_connections",
        "get_network_interfaces",
        "get_process_list",
        "get_process_detail",
        "get_service_status",
        "get_file_list",
        "read_file",
        "get_logs",
        "run_command",
    ],
}

ROLE_RESOURCE_ALLOWLIST: Dict[str, List[str]] = {
    "admin": ["resource://system/summary", "resource://knowledge/base", "resource://audit/events"],
    "auditor": ["resource://system/summary", "resource://knowledge/base", "resource://audit/events"],
    "deployer": ["resource://system/summary", "resource://knowledge/base"],
}

ROLE_PROMPT_ALLOWLIST: Dict[str, List[str]] = {
    "admin": ["incident_analysis", "log_triage", "risk_review"],
    "auditor": ["incident_analysis", "log_triage", "risk_review"],
    "deployer": ["incident_analysis", "log_triage", "risk_review"],
}


def can_access_tool(role: str, tool_name: str) -> bool:
    return tool_name in ROLE_TOOL_ALLOWLIST.get(role, ROLE_TOOL_ALLOWLIST["admin"])


def can_access_resource(role: str, uri: str) -> bool:
    return uri in ROLE_RESOURCE_ALLOWLIST.get(role, ROLE_RESOURCE_ALLOWLIST["admin"])


def can_access_prompt(role: str, prompt_name: str) -> bool:
    return prompt_name in ROLE_PROMPT_ALLOWLIST.get(role, ROLE_PROMPT_ALLOWLIST["admin"])
