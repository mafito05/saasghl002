# routers/instance.py
import docker
import secrets
import socket
import time
import requests
import os
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, HttpUrl, Field

from logger_config import logger
from database.connection import get_db
from models.user import User
from models.instance import Instance as InstanceModel
from schemas.instance import Instance as InstanceSchema
from routers.auth import get_current_active_user

router = APIRouter(prefix="/instances", tags=["Instances"])

DOCKER_NETWORK_NAME = os.getenv("DOCKER_NETWORK", "my_saas_network")

def find_free_port():
    """Encuentra un puerto libre en el host."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]

def wait_for_instance_ready(instance_url: str, timeout: int = 40):
    """Espera a que una instancia responda a las peticiones HTTP."""
    start_time = time.time()
    health_check_url = f"{instance_url}/api/server/status"
    logger.info(f"Verificando la instancia en: {health_check_url}")
    
    while time.time() - start_time < timeout:
        try:
            response = requests.get(health_check_url, timeout=3)
            if response.status_code == 200:
                logger.info(f"¡ÉXITO! La instancia en {instance_url} está lista y respondiendo.")
                return True
        except requests.exceptions.RequestException as e:
            logger.info(f"Esperando a la instancia en {instance_url}... ({e})")
        
        time.sleep(2)
        
    raise TimeoutError(f"La nueva instancia de API no respondió a tiempo en {instance_url}")

@router.post("/", response_model=InstanceSchema, status_code=status.HTTP_201_CREATED)
def create_instance(db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    logger.info("Iniciando el proceso de creación de instancia con la API estable...")
    
    existing_instance = db.query(InstanceModel).filter(InstanceModel.owner_id == current_user.id).first()
    if existing_instance:
        raise HTTPException(status_code=400, detail="El usuario ya tiene una instancia activa.")

    container = None
    try:
        instance_port = find_free_port()
        instance_name = f"wa_instance_{current_user.id}_{secrets.token_hex(4)}"
        instance_api_key = secrets.token_hex(16)
        
        client = docker.from_env()

        public_url = f"http://localhost:{instance_port}"
        webhook_url = f"http://saas_backend:8000/api/webhooks/waha/{instance_name}"

        container = client.containers.run(
            "devlikeapro/whatsapp-http-api:latest",
            detach=True,
            name=instance_name,
            ports={f"3000/tcp": instance_port},
            environment={
                "WAHA_API_KEY": instance_api_key,
                "WAHA_WEBHOOK_URL": webhook_url,
                "WAHA_PUBLIC_URL": public_url,
            },
            network=DOCKER_NETWORK_NAME
        )
        logger.info(f"Contenedor '{container.name}' (ID: {container.id[:12]}) iniciado exitosamente.")

        instance_url_for_requests = f"http://host.docker.internal:{instance_port}"
        
        wait_for_instance_ready(instance_url_for_requests)
        
        new_instance = InstanceModel(
            instance_name=instance_name,
            instance_url=public_url,
            api_key=instance_api_key,
            owner_id=current_user.id
        )
        db.add(new_instance)
        db.commit()
        db.refresh(new_instance)
        logger.info(f"Instancia '{instance_name}' guardada en la base de datos principal.")

        return new_instance

    except Exception as e:
        if container:
            try: 
                logs = container.logs().decode('utf-8')
                logger.error(f"Logs del contenedor fallido '{container.name}':\n{logs}")
                container.stop()
                container.remove()
            except Exception as cleanup_error:
                logger.error(f"Error durante la limpieza del contenedor: {cleanup_error}")
        
        logger.error(f"Error catastrófico durante la creación de la instancia: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error inesperado al crear la instancia: {str(e)}")


# --- Endpoints para configurar la instancia ---

class GhlApiKeyUpdate(BaseModel):
    api_key: str = Field(..., min_length=32, description="GoHighLevel Agency o Location API Key")

@router.patch("/ghl_key", response_model=InstanceSchema)
def set_ghl_api_key(
    key_data: GhlApiKeyUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Permite al usuario configurar su API Key de GoHighLevel para su instancia.
    La clave se guarda de forma segura y encriptada.
    """
    instance = db.query(InstanceModel).filter(InstanceModel.owner_id == current_user.id).first()
    if not instance:
        raise HTTPException(status_code=404, detail="Instancia no encontrada. Debes crear una primero.")
    
    # La clave se encriptará automáticamente gracias al setter del modelo
    instance.ghl_api_key = key_data.api_key
    
    db.commit()
    db.refresh(instance)
    logger.info(f"API Key de GoHighLevel actualizada para la instancia '{instance.instance_name}'.")
    
    return instance


class WebhookUpdate(BaseModel):
    webhook_url: HttpUrl

@router.patch("/webhook", response_model=InstanceSchema)
def set_customer_webhook(
    webhook_data: WebhookUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Permite al usuario configurar la URL de su webhook (para n8n, etc.).
    """
    instance = db.query(InstanceModel).filter(InstanceModel.owner_id == current_user.id).first()
    if not instance:
        raise HTTPException(status_code=404, detail="Instancia no encontrada.")
    
    instance.webhook_url = str(webhook_data.webhook_url)
    db.commit()
    db.refresh(instance)
    logger.info(f"Webhook actualizado para la instancia '{instance.instance_name}' a: {instance.webhook_url}")
    
    return instance