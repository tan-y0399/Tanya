import uuid
from datetime import datetime


def generate_trace_id() -> str:
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
    return f"trace-{ts}-{uuid.uuid4().hex[:8]}"
