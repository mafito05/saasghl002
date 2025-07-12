import logger_config
import os
from dotenv import load_dotenv

# Carga las variables de entorno ANTES que cualquier otra cosa
load_dotenv()

from fastapi import FastAPI
from database.connection import Base, engine

# 👇 Importamos todos los routers en una sola línea
from routers import auth, instance, webhook, ghl_oauth

# Importamos los modelos para que SQLAlchemy cree las tablas
from models import user, instance as instance_model
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="SaaS para Evolution API y GHL",
    version="0.1.0",
)

@app.get("/")
def read_root():
    return {"status": "ok", "message": "Servidor del SaaS funcionando correctamente."}

# Incluye los routers en la aplicación principal
app.include_router(auth.router, prefix="/api")
app.include_router(instance.router, prefix="/api")
app.include_router(webhook.router, prefix="/api")
app.include_router(ghl_oauth.router, prefix="/api")    