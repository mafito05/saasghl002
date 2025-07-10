# models/instance.py
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from database.connection import Base

class Instance(Base):
    __tablename__ = "instances"

    id = Column(Integer, primary_key=True, index=True)
    instance_name = Column(String, unique=True, nullable=False)
    instance_url = Column(String, nullable=False)
    api_key = Column(String, nullable=False)
    is_connected = Column(Boolean, default=False)
    owner_id = Column(Integer, ForeignKey("users.id"))