# routers/ghl_actions.py
from fastapi import APIRouter, Request, Depends
from sqlalchemy.orm import Session
import json

from logger_config import logger
from database.connection import get_db
from models.instance import Instance as InstanceModel
from services import waha_service

router = APIRouter(prefix="/ghl-actions", tags=["GHL Actions"])

@router.post("/send-message")
async def handle_send_request(request: Request, db: Session = Depends(get_db)):
    """
    Este endpoint es llamado por GHL cuando un usuario quiere enviar un mensaje.
    """
    payload = await request.json()
    logger.info("==================== GHL -> SEND-MESSAGE ====================")
    logger.info(f"Petición de envío recibida desde GHL: {json.dumps(payload, indent=2)}")

    try:
        # Extraemos los datos que GHL nos envía
        location_id = payload.get("locationId")
        contact_id = payload.get("contactId")
        phone_number = payload.get("phone") # GHL envía el número del destinatario
        message = payload.get("message")

        if not all([location_id, phone_number, message]):
            logger.error(f"Faltan datos en el webhook de GHL: locationId, phone o message.")
            return {"status": "error", "message": "Payload incompleto"}

        # Buscamos la instancia de WAHA que corresponde a esta location de GHL
        instance = db.query(InstanceModel).filter(InstanceModel.ghl_location_id == location_id).first()
        if not instance:
            logger.error(f"No se encontró una instancia de WAHA para la locationId: {location_id}")
            return {"status": "error", "message": "Instancia no configurada"}
            
        # Usamos nuestro nuevo servicio para enviar el mensaje por WhatsApp
        success = await waha_service.send_whatsapp_message(
            instance_url=instance.instance_url,
            api_key=instance.api_key,
            to_number=phone_number,
            message=message
        )

        if success:
            return {"status": "success"}
        else:
            return {"status": "error", "message": "Fallo al enviar el mensaje por WAHA"}

    except Exception as e:
        logger.error(f"Excepción al procesar el webhook de envío de GHL: {e}", exc_info=True)
        return {"status": "error", "message": "Error interno del servidor"}