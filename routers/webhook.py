from fastapi import APIRouter, Request, Path, HTTPException, BackgroundTasks, Depends
from pydantic import BaseModel, Field
from typing import Optional
from sqlalchemy.orm import Session

from logger_config import logger
from database.connection import get_db
from models.instance import Instance as InstanceModel
from services import gohighlevel_service

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])

class MessageData(BaseModel):
    body: str

class FromData(BaseModel):
    id: str
    name: str

class MessagePayload(BaseModel):
    data: MessageData
    from_data: FromData = Field(..., alias='from')

class WahaWebhookPayload(BaseModel):
    event: str
    session: str
    payload: MessagePayload

@router.post("/waha/{instance_name}")
async def waha_webhook_receiver(
    payload: WahaWebhookPayload,
    instance_name: str = Path(..., description="El nombre de la instancia que recibe el webhook"),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db)
):
    logger.info(f"Webhook recibido para la instancia '{instance_name}' con el evento '{payload.event}'")
    
    if payload.event != 'message':
        logger.info(f"Evento '{payload.event}' ignorado.")
        return {"status": "event ignored"}

    background_tasks.add_task(
        process_incoming_message,
        instance_name=instance_name,
        payload=payload,
        db=db
    )

    return {"status": "message received and processing"}

async def process_incoming_message(instance_name: str, payload: WahaWebhookPayload, db: Session):
    logger.info(f"Procesando mensaje en segundo plano para la instancia: {instance_name}")

    # 1. Buscar la instancia y su GHL API Key en nuestra DB
    instance = db.query(InstanceModel).filter(InstanceModel.instance_name == instance_name).first()
    if not instance:
        logger.error(f"Se recibió un webhook para una instancia desconocida: {instance_name}")
        return

    ghl_api_key = instance.ghl_api_key
    if not ghl_api_key:
        logger.warning(f"La instancia '{instance_name}' no tiene una GHL API Key configurada. Ignorando mensaje.")
        return

    # 2. Extraer datos del payload
    phone_number = payload.payload.from_data.id.split('@')[0]
    sender_name = payload.payload.from_data.name
    message_body = payload.payload.data.body
    
    logger.info(f"Mensaje de: {sender_name} ({phone_number})")
    logger.info(f"Mensaje: {message_body}")

    # 3. Buscar contacto en GoHighLevel usando la clave específica de la instancia
    contact = await gohighlevel_service.search_contact_by_phone(phone_number, ghl_api_key)

    # 4. Si no existe, crearlo
    if not contact:
        logger.info(f"Creando nuevo contacto en GHL para {phone_number}")
        contact = await gohighlevel_service.create_contact_in_ghl(
            phone=phone_number,
            name=sender_name,
            ghl_api_key=ghl_api_key
        )

    if not contact or not contact.get("id"):
        logger.error(f"No se pudo encontrar o crear un contacto en GHL para {phone_number}")
        return

    contact_id = contact["id"]

    # 5. Añadir el mensaje a la conversación del contacto en GHL
    success = await gohighlevel_service.add_inbound_message_to_ghl(
        contact_id=contact_id,
        message_body=message_body,
        ghl_api_key=ghl_api_key
    )

    if success:
        logger.info(f"Proceso de webhook completado con éxito para el contacto {contact_id}")
    else:
        logger.error(f"Falló el envío del mensaje a GHL para el contacto {contact_id}")
