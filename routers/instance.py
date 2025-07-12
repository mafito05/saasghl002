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
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]

def wait_for_instance_ready(instance_url: str, api_key: str, timeout: int = 60):
    start_time = time.time()
    health_check_url = f"{instance_url}/api/server/status"
    logger.info(f"Verificando la instancia en: {health_check_url}")
    
    while time.time() - start_time < timeout:
        try:
            response = requests.get(health_check_url, headers={"X-Api-Key": api_key}, timeout=5)
            if response.status_code == 200:
                logger.info(f"¡ÉXITO! La instancia en {instance_url} está lista.")
                return True
        except requests.exceptions.RequestException:
            logger.info(f"Esperando a la instancia en {instance_url}...")
        
        time.sleep(2)
        
    raise TimeoutError(f"La nueva instancia de API no respondió a tiempo en {instance_url}")

def configure_waha_session(instance_url: str, api_key: str, webhook_target_url: str):
    """
    Configura la sesión 'default' de WAHA para que use nuestro webhook.
    """
    endpoint = f"{instance_url}/api/sessions/default"
    headers = {"X-Api-Key": api_key, "Content-Type": "application/json"}
    payload = {
      "config": {
        "webhooks": [
          {
            "url": webhook_target_url,
            "events": [
              "message",
              "session.status"
            ]
          }
        ]
      }
    }
    
    logger.info(f"Configurando sesión 'default' para la instancia en {instance_url}...")
    logger.info(f"URL del Webhook a configurar: {webhook_target_url}")

    try:
        response = requests.put(endpoint, headers=headers, json=payload, timeout=10)
        response.raise_for_status()
        logger.info(f"Sesión 'default' configurada exitosamente. Respuesta: {response.json()}")
    except requests.exceptions.RequestException as e:
        logger.error(f"FALLO CRÍTICO al configurar la sesión de la instancia: {e}")
        raise

@router.post("/", response_model=InstanceSchema, status_code=status.HTTP_201_CREATED)
def create_instance(db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    logger.info("Iniciando el proceso de creación de instancia...")
    
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
        
        container = client.containers.run(
            "devlikeapro/whatsapp-http-api:latest",
            detach=True,
            name=instance_name,
            ports={f"3000/tcp": instance_port},
            environment={"WAHA_API_KEY": instance_api_key},
            network=DOCKER_NETWORK_NAME,
            extra_hosts={"host.docker.internal": "host-gateway"}
        )
        logger.info(f"Contenedor '{container.name}' iniciado exitosamente.")

        instance_url_for_api = f"http://host.docker.internal:{instance_port}"
        
        wait_for_instance_ready(instance_url_for_api, instance_api_key)
        
        # --- CORRECCIÓN FINAL Y DEFINITIVA ---
        # Usamos 'host.docker.internal' que es una URL válida para el validador de WAHA
        # y apunta correctamente a nuestro backend desde dentro de la red de Docker.
        webhook_target_url = f"http://host.docker.internal:8000/api/webhooks/waha/{instance_name}"
        configure_waha_session(instance_url_for_api, instance_api_key, webhook_target_url)

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
                container.stop(); container.remove()
            except: pass
        
        logger.error(f"Error catastrófico durante la creación: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error inesperado: {str(e)}")
