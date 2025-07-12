# models/user.py
from sqlalchemy import Column, Integer, String, Boolean
from sqlalchemy.orm import relationship
from database.connection import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)

    # --- CORRECCIÓN ---
    # Añadimos la relación que faltaba.
    # Esto le dice a SQLAlchemy que un usuario puede tener muchas instancias.
    # "back_populates" conecta esta relación con la propiedad "owner" en el modelo Instance.
    instances = relationship("Instance", back_populates="owner", cascade="all, delete-orphan")
