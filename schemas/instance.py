# schemas/instance.py
from pydantic import BaseModel, HttpUrl
from typing import Optional

# Esquema para la respuesta de la API.
# Define cómo se verán los datos de la instancia cuando se envíen al cliente.
class Instance(BaseModel):
    id: int
    instance_name: str
    instance_url: HttpUrl
    api_key: str
    webhook_url: Optional[HttpUrl] = None
    
    # --- CORRECCIÓN 2 ---
    # El error 'ResponseValidationError' ocurría porque este campo era requerido
    # pero no se proporcionaba ningún valor al crear la instancia.
    # Al añadir un valor por defecto, solucionamos el error.
    # 'False' es un valor correcto, ya que una instancia nueva nunca está conectada.
    is_connected: bool = False

    class Config:
        # Permite que el modelo Pydantic lea los datos desde un objeto de SQLAlchemy.
        from_attributes = True

# Esquema para la creación de instancias (si se necesitara en el futuro).
class InstanceCreate(BaseModel):
    pass
