from __future__ import annotations

from typing import Any, Dict, List

from app.api.routes.knowledge import seed_knowledge
from app.mcp.audit import record_mcp_event


RESOURCE_DEFINITIONS: List[Dict[str, Any]] = [
    {
        "uri": "resource://system/summary",
        "name": "system_summary",
        "description": "System summary and platform overview",
        "mimeType": "application/json",
    },
    {
        "uri": "resource://knowledge/base",
        "name": "knowledge_base",
        "description": "Knowledge base articles and operational SOP",
        "mimeType": "application/json",
    },
    {
        "uri": "resource://audit/events",
        "name": "audit_events",
        "description": "MCP audit events for traceability",
        "mimeType": "application/json",
    },
]


async def read_resource(uri: str, db=None) -> Dict[str, Any]:
    if uri == "resource://system/summary":
        data = {
            "name": "KylinOps",
            "description": "Intelligent operations platform",
            "capabilities": [
                "system monitoring",
                "process inspection",
                "log retrieval",
                "service management",
                "knowledge base",
                "approval workflow",
            ],
        }
        record_mcp_event("resource_read", {"uri": uri, "status": "ok"})
        return {"success": True, "data": data}
    if uri == "resource://knowledge/base":
        if db is None:
            record_mcp_event("resource_read", {"uri": uri, "status": "missing_db"})
            return {"success": False, "error": "Database session is required"}
        await seed_knowledge(db)
        record_mcp_event("resource_read", {"uri": uri, "status": "ok"})
        return {"success": True, "data": {"message": "Knowledge base seeded or available via API"}}
    if uri == "resource://audit/events":
        from app.mcp.audit import list_mcp_events

        events = list_mcp_events()
        record_mcp_event("resource_read", {"uri": uri, "status": "ok", "count": len(events)})
        return {"success": True, "data": {"events": events, "count": len(events)}}
    record_mcp_event("resource_read", {"uri": uri, "status": "unknown"})
    return {"success": False, "error": f"Unknown resource: {uri}"}
