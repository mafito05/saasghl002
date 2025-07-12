# schemas/webhook.py
from pydantic import BaseModel, Field
from typing import Optional

# Hacemos los campos opcionales para capturar el payload incluso si no coincide exactamente
class MessageData(BaseModel):
    body: Optional[str] = None

class FromData(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None

class MessagePayload(BaseModel):
    data: Optional[MessageData] = None
    from_data: Optional[FromData] = Field(None, alias='from')

class WahaWebhookPayload(BaseModel):
    event: Optional[str] = None
    session: Optional[str] = None
    payload: Optional[MessagePayload] = None