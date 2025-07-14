# routers/webhook.py
from fastapi import APIRouter, Request, Path, BackgroundTasks, Depends
from sqlalchemy.orm import Session
import json

from logger_config import logger
from database.connection import get_db
from models.instance import Instance as InstanceModel
from services import gohighlevel_service

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])

async def process_message(instance_name: str, payload: dict, db: Session):
    """
    Procesa mensajes entrantes y salientes de chats individuales.
    """
    logger.info(f"--- [BG-TASK] Iniciando procesado para la instancia '{instance_name}' ---")

    # --- 1. EXTRACCIÓN DE DATOS ---
    try:
        message_payload = payload.get("payload", {})
        is_from_me = message_payload.get("fromMe", False)
        contact_id_full = message_payload.get("to") if is_from_me else message_payload.get("from", "")
        phone_number = contact_id_full.split('@')[0]
        message_body = message_payload.get("body") or message_payload.get("caption", "")
        sender_name = message_payload.get("_data", {}).get("notifyName") or phone_number

        if not message_body.strip() and message_payload.get("hasMedia"):
            message_body = f"[Archivo Multimedia Enviado/Recibido]"
        
        direction_log = "SALIENTE" if is_from_me else "ENTRANTE"
        logger.info(f"Datos ({direction_log}) -> Contacto: {sender_name} ({phone_number}), Mensaje: '{message_body}'")

        if not message_body.strip():
            logger.info("El cuerpo del mensaje está vacío. No se procesará.")
            return
            
    except Exception as e:
        logger.error(f"Error al extraer datos del payload: {e}", exc_info=True)
        return

    # --- 2. LÓGICA DE GOHIGHLEVEL ---
    try:
        instance = db.query(InstanceModel).filter(InstanceModel.instance_name == instance_name).first()
        if not instance or not all([instance.ghl_access_token, instance.ghl_location_id, instance.ghl_user_id]):
            logger.error(f"¡FALLO CRÍTICO! La instancia '{instance_name}' no está completamente conectada a GHL.")
            return

        contact = await gohighlevel_service.get_or_create_contact_in_ghl(
            phone=phone_number, name=sender_name,
            location_id=instance.ghl_location_id, access_token=instance.ghl_access_token
        )
        if not contact or not contact.get("id"):
            logger.error(f"¡FALLO! No se pudo obtener ni crear el contacto en GHL para {phone_number}.")
            return
        contact_id = contact["id"]
        
        logger.info(f"Contacto en GHL listo. ID: {contact_id}. Procediendo a añadir el mensaje...")

        # Esta es la llamada que causaba el error. Ahora la función existe.
        success = await gohighlevel_service.add_message_to_ghl(
            contact_id=contact_id,
            message_body=message_body,
            access_token=instance.ghl_access_token,
            user_id=instance.ghl_user_id,
            direction="outbound" if is_from_me else "inbound"
        )

        if success:
            logger.info(f"✅ ¡ÉXITO TOTAL! Mensaje ({direction_log}) del contacto {contact_id} procesado.")
        else:
            logger.error(f"❌ ¡FALLO! El envío del mensaje ({direction_log}) a GHL para el contacto {contact_id} no tuvo éxito.")

    except Exception as e:
        logger.error(f"Se produjo una excepción inesperada durante el procesamiento de GHL: {e}", exc_info=True)
    finally:
        logger.info(f"==================== FIN DE TAREA PARA '{instance_name}' ====================")


@router.post("/waha/{instance_name}")
async def waha_webhook_receiver(
    request: Request,
    background_tasks: BackgroundTasks,
    instance_name: str = Path(..., description="El nombre de la instancia que recibe el webhook"),
    db: Session = Depends(get_db)
):
    """
    Punto de entrada para los webhooks de WAHA. Filtra silenciosamente y solo loguea/procesa
    los mensajes de chat individuales.
    """
    raw_payload = await request.json()

    # --- FILTRO SILENCIOSO FINAL ---
    payload_content = raw_payload.get("payload", {})
    from_id = payload_content.get("from", "")
    
    if from_id == 'status@broadcast' or "@g.us" in from_id:
        return {"status": "event_ignored_silently"}

    if not payload_content.get("body") and not payload_content.get("caption"):
         return {"status": "event_ignored_silently_no_body"}
    
    logger.info("==================== INICIO DE WEBHOOK DE CHAT ====================")
    logger.info(f"Webhook de chat válido recibido para la instancia '{instance_name}'")
    logger.info(f"Payload crudo procesado:\n{json.dumps(raw_payload, indent=2)}")

    background_tasks.add_task(process_message, instance_name, raw_payload, db)
    logger.info("Webhook validado y encolado para procesamiento.")
    
    return {"status": "message_queued"}