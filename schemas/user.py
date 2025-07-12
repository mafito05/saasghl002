# schemas/user.py
from pydantic import BaseModel, EmailStr
from typing import List

# --- CORRECCIÓN: Se importa el schema de Instance para evitar errores de referencia circular ---
from .instance import Instance

class UserBase(BaseModel):
    email: EmailStr

class UserCreate(UserBase):
    password: str

class User(UserBase):
    id: int
    is_active: bool
    # Se añade la lista de instancias para que la respuesta sea completa
    instances: List[Instance] = []

    class Config:
        # Permite que el modelo Pydantic lea los datos desde un objeto de SQLAlchemy
        from_attributes = True
