# routers/instance.py (Usando la API Estable)
import docker
import secrets
import socket
import time
import requests
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from logger_config import logger 

from database.connection import get_db
from models.user import User
from models.instance import Instance as InstanceModel
from schemas.instance import Instance as InstanceSchema
from routers.auth import get_current_active_user 

router = APIRouter(prefix="/instances", tags=["Instances"])

def find_free_port():
    """Encuentra un puerto libre en el host."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]

def wait_for_instance_ready(instance_url: str, timeout: int = 30):
    """Espera a que una instancia responda a las peticiones HTTP."""
    start_time = time.time()
    # El endpoint de salud de esta nueva API es /api/status
    health_check_url = f"{instance_url}/api/status" 
    while time.time() - start_time < timeout:
        try:
            response = requests.get(health_check_url, timeout=2)
            if response.status_code == 200:
                logger.info(f"La instancia en {instance_url} está lista.")
                return True
        except requests.exceptions.ConnectionError:
            logger.info(f"Esperando a la instancia en {instance_url}...")
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

        # 👇 USAMOS LA NUEVA IMAGEN Y UNA CONFIGURACIÓN MÁS SIMPLE
        container = client.containers.run(
            "devlikeapro/whatsapp-http-api:latest",
            detach=True,
            name=instance_name,
            ports={f"3000/tcp": instance_port}, # Esta imagen usa el puerto 3000
            environment={
                "WHATSAPP_API_KEY": instance_api_key,
                # Esta API sí lee el webhook desde las variables de entorno
                "WHATSAPP_API_WEBHOOK_URL": f"http://host.docker.internal:8000/api/webhooks/wa/{instance_name}"
            }
        )
        logger.info(f"Contenedor '{container.name}' (ID: {container.id[:12]}) iniciado exitosamente.")

        instance_url = f"http://localhost:{instance_port}"
        
        # Usamos nuestro bucle de reintentos para esperar a que esté lista
        wait_for_instance_ready(instance_url)
        
        # Guardamos la instancia en nuestra BD
        new_instance = InstanceModel(
            instance_name=instance_name,
            instance_url=instance_url,
            api_key=instance_api_key,
            owner_id=current_user.id
        )
        db.add(new_instance)
        db.commit()
        db.refresh(new_instance)
        logger.info(f"Instancia guardada en la base de datos con ID: {new_instance.id}")

        return new_instance

    except Exception as e:
        if container:
            try: container.stop(); container.remove()
            except: pass
        logger.error(f"Error durante la creación de la instancia: {e}")
        raise HTTPException(status_code=500, detail=f"Error inesperado: {str(e)}")