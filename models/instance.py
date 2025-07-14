# models/instance.py
from sqlalchemy import Column, Integer, String, ForeignKey, LargeBinary, Boolean
from sqlalchemy.orm import relationship
from database.connection import Base
# La encriptación se manejará en el router para más claridad

class Instance(Base):
    __tablename__ = "instances"

    id = Column(Integer, primary_key=True, index=True)
    instance_name = Column(String, unique=True, index=True, nullable=False)
    instance_url = Column(String, nullable=False)
    api_key = Column(String, nullable=False) # API Key para la instancia de WAHA
    
    # --- NUEVOS CAMPOS PARA OAUTH ---
    # Guardaremos los tokens de GHL aquí
    ghl_access_token = Column(String, nullable=True)
    ghl_refresh_token = Column(String, nullable=True)
    ghl_location_id = Column(String, nullable=True, index=True) # Para saber a qué sub-cuenta pertenece
    ghl_user_id = Column(String)# <--- AÑADE ESTA LÍNEA

    webhook_url = Column(String, nullable=True) # Webhook para n8n, etc.
    is_connected = Column(Boolean, default=False)

    owner_id = Column(Integer, ForeignKey("users.id"))
    owner = relationship("User", back_populates="instances")
