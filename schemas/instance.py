# schemas/instance.py
from pydantic import BaseModel

class Instance(BaseModel):
    id: int
    instance_name: str
    instance_url: str
    api_key: str
    is_connected: bool
    owner_id: int

    # Esta línea mágica le permite a Pydantic leer desde
    # un objeto de base de datos (ORM)
    class Config:
        from_attributes = True