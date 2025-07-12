# routers/webhook.py
from fastapi import APIRouter, Request, Path, BackgroundTasks, Depends
from sqlalchemy.orm import Session
import json

from logger_config import logger
from database.connection import get_db
from models.instance import Instance as InstanceModel
from services import gohighlevel_service
from schemas.webhook import WahaWebhookPayload

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])

@router.post("/waha/{instance_name}")
async def waha_webhook_receiver(
    request: Request,
    instance_name: str = Path(..., description="El nombre de la instancia que recibe el webhook"),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db)
):
    logger.info("==================== INICIO DE WEBHOOK ====================")
    logger.info(f"Webhook recibido para la instancia '{instance_name}'")
    
    raw_payload = await request.json()
    logger.info(f"Payload crudo recibido:\n{json.dumps(raw_payload, indent=2)}")

    try:
        payload = WahaWebhookPayload.model_validate(raw_payload)
    except Exception as e:
        logger.error(f"Error al validar el payload con Pydantic: {e}")
        return {"status": "pydantic validation error"}

    # --- CORRECCIÓN FINAL ---
    # Ignoramos eventos que no son mensajes y también los mensajes de "status@broadcast"
    if payload.event != 'message' or (payload.payload and payload.payload.from_data and payload.payload.from_data.id == 'status@broadcast'):
        logger.info(f"Evento '{payload.event}' o mensaje de status ignorado. No se procesará.")
        return {"status": "event ignored"}

    background_tasks.add_task(process_incoming_message, instance_name=instance_name, payload=payload, db=db)
    return {"status": "message received, processing in background"}

async def process_incoming_message(instance_name: str, payload: WahaWebhookPayload, db: Session):
    logger.info("--- Iniciando procesado en segundo plano ---")

    instance = db.query(InstanceModel).filter(InstanceModel.instance_name == instance_name).first()
    if not instance:
        logger.error(f"¡FALLO! Instancia desconocida: {instance_name}")
        return

    logger.info(f"Instancia '{instance.instance_name}' encontrada en la base de datos.")

    access_token = instance.ghl_access_token
    location_id = instance.ghl_location_id
    if not all([access_token, location_id]):
        logger.warning(f"¡FALLO! La instancia '{instance_name}' no está conectada a GHL (faltan tokens o location_id).")
        return
        
    logger.info(f"Conexión a GHL encontrada para la ubicación: {location_id}")

    if not payload.payload or not payload.payload.from_data or not payload.payload.data:
        logger.error("¡FALLO! El payload no tiene la estructura esperada.")
        return

    # En este punto, ya hemos filtrado los 'status@broadcast'
    phone_number = payload.payload.from_data.id.split('@')[0]
    sender_name = payload.payload.from_data.name
    message_body = payload.payload.data.body
    
    if not all([phone_number, sender_name, message_body]):
        logger.error(f"¡FALLO! Faltan datos esenciales en el payload: phone='{phone_number}', name='{sender_name}', body='{message_body}'")
        return

    logger.info(f"Datos extraídos -> De: {sender_name} ({phone_number}), Mensaje: '{message_body}'")

    contact = await gohighlevel_service.search_contact_by_phone(phone_number, access_token)

    if not contact:
        logger.info("Contacto no encontrado. Creando nuevo contacto en GHL...")
        contact = await gohighlevel_service.create_contact_in_ghl(
            phone=phone_number,
            name=sender_name,
            location_id=location_id,
            access_token=access_token
        )

    if not contact or not contact.get("id"):
        logger.error(f"¡FALLO CATASTRÓFICO! No se pudo encontrar o crear un contacto en GHL para {phone_number}.")
        return

    contact_id = contact["id"]
    logger.info(f"Contacto en GHL listo. ID: {contact_id}. Añadiendo mensaje...")

    success = await gohighlevel_service.add_inbound_message_to_ghl(
        contact_id=contact_id,
        message_body=message_body,
        access_token=access_token
    )

    if success:
        logger.info(f"¡ÉXITO TOTAL! Proceso de webhook completado para el contacto {contact_id}.")
    else:
        logger.error(f"¡FALLO! El envío del mensaje a GHL para el contacto {contact_id} no tuvo éxito.")
    
    logger.info("==================== FIN DE WEBHOOK ====================")
