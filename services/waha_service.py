# services/waha_service.py
import httpx
from logger_config import logger
import json

async def send_whatsapp_message(instance_url: str, api_key: str, to_number: str, message: str):
    """
    Envía un mensaje de texto a un número de WhatsApp usando una instancia de WAHA.
    """
    if not all([instance_url, api_key, to_number, message]):
        logger.error("Faltan datos para enviar el mensaje de WhatsApp desde WAHA.")
        return False

    # Aseguramos que el número tenga el formato correcto para WAHA
    if not to_number.endswith('@c.us'):
        to_number = f"{to_number}@c.us"

    url = f"{instance_url}/api/sendText"
    headers = {"X-Api-Key": api_key, "Content-Type": "application/json"}
    payload = {"chatId": to_number, "text": message}

    try:
        logger.info(f"WAHA API Call: Enviando mensaje a {to_number}")
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            logger.info(f"WAHA API Response: Mensaje enviado a {to_number} exitosamente. Response: {json.dumps(response.json(), indent=2)}")
            return True
    except httpx.HTTPStatusError as e:
        logger.error(f"Error HTTP al enviar mensaje con WAHA. Status: {e.response.status_code}, Response: {e.response.text}")
        return False
    except Exception as e:
        logger.error(f"Excepción inesperada en send_whatsapp_message: {e}", exc_info=True)
        return False