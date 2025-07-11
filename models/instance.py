from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.types import LargeBinary
from database.connection import Base
import os
from cryptography.fernet import Fernet

# --- ENCRYPTION HELPERS ---
# Es crucial que esta clave se guarde de forma segura como un secreto y no se pierda.
# Idealmente, se carga desde el entorno.
ENCRYPTION_KEY_STR = os.getenv("FIELD_ENCRYPTION_KEY", "T2l-58K_g9u_4sA92e-r_sEcReT_kEy_32bYt")
if len(ENCRYPTION_KEY_STR.encode()) < 32:
    raise ValueError("La clave de encriptación debe tener al menos 32 bytes")
ENCRYPTION_KEY = ENCRYPTION_KEY_STR.encode()[:32] # Asegurarse de que tenga 32 bytes
fernet = Fernet(ENCRYPTION_KEY)

def encrypt_field(data: str) -> bytes:
    """Encripta un campo de texto."""
    if not data:
        return None
    return fernet.encrypt(data.encode())

def decrypt_field(encrypted_data: bytes) -> str:
    """Desencripta un campo de texto."""
    if not encrypted_data:
        return None
    return fernet.decrypt(encrypted_data).decode()

# --- MODEL ---

class Instance(Base):
    __tablename__ = "instances"

    id = Column(Integer, primary_key=True, index=True)
    instance_name = Column(String, unique=True, index=True, nullable=False)
    instance_url = Column(String, nullable=False)
    api_key = Column(String, nullable=False) # API Key para la instancia de WAHA
    
    # Nuevo campo para la API Key de GoHighLevel, almacenada de forma encriptada
    _ghl_api_key = Column("ghl_api_key", LargeBinary, nullable=True)
    
    webhook_url = Column(String, nullable=True) # Webhook para n8n, etc.

    owner_id = Column(Integer, ForeignKey("users.id"))
    owner = relationship("User", back_populates="instances")

    @property
    def ghl_api_key(self) -> str:
        """Propiedad para obtener la clave desencriptada."""
        return decrypt_field(self._ghl_api_key)

    @ghl_api_key.setter
    def ghl_api_key(self, value: str):
        """Propiedad para guardar la clave encriptada."""
        self._ghl_api_key = encrypt_field(value)