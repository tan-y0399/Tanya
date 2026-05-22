from typing import Optional
from pydantic import BaseModel


class BaseResponse(BaseModel):
    code: int = 0
    message: str = "success"
    data: Optional[object] = None
    traceId: Optional[str] = None


class PageData(BaseModel):
    items: list
    total: int
    page: int
    size: int
