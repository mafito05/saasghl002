# services/gohighlevel_service.py
import os
import httpx
import json
from typing import Optional, Dict, Any
from logger_config import logger

GHL_API_URL = "https://services.leadconnectorhq.com"
GHL_API_TIMEOUT = 60.0

async def _get_auth_headers(access_token: str) -> Dict[str, Any]:
    if not access_token:
        raise ValueError("Se requiere un access_token de GHL para hacer la petición.")
    return {
        "Authorization": f"Bearer {access_token}",
        "Version": "2021-07-28",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

async def get_or_create_contact_in_ghl(phone: str, name: str, location_id: str, access_token: str) -> Optional[Dict[str, Any]]:
    # Esta función ya está perfecta, no se toca.
    headers = await _get_auth_headers(access_token)
    create_payload = { "name": name, "phone": phone, "locationId": location_id, "source": "WhatsApp SaaS Integration" }
    async with httpx.AsyncClient(timeout=GHL_API_TIMEOUT) as client:
        try:
            logger.info(f"GHL API Call (get_or_create_contact): Intentando crear/obtener contacto para {phone}")
            response = await client.post(f"{GHL_API_URL}/contacts/", headers=headers, json=create_payload)
            response.raise_for_status()
            contact_data = response.json().get("contact")
            logger.info(f"GHL API Response: Contacto creado exitosamente, ID: {contact_data.get('id')}")
            return contact_data
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 400 and "does not allow duplicated contacts" in e.response.json().get("message", ""):
                existing_contact_id = e.response.json().get("meta", {}).get("contactId")
                if existing_contact_id:
                    logger.info(f"Contacto ya existente. ID recuperado del error: {existing_contact_id}")
                    return {"id": existing_contact_id}
            logger.error(f"Error HTTP no manejado al obtener contacto ({e.response.status_code}): {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"Excepción inesperada en get_or_create_contact: {e}", exc_info=True)
            return None

# --- FUNCIÓN DE MENSAJES FINAL Y DEFINITIVA ---
async def add_message_to_ghl(contact_id: str, message_body: str, access_token: str, user_id: str, direction: str) -> bool:
    """
    Añade un mensaje (entrante o saliente) a una conversación.
    """
    try:
        headers = await _get_auth_headers(access_token)
        
        # Paso 1: Buscar la conversación para obtener el conversationId
        conversation_id = None
        async with httpx.AsyncClient(timeout=GHL_API_TIMEOUT) as client:
            search_url = f"{GHL_API_URL}/conversations/search?contactId={contact_id}"
            logger.info(f"Buscando conversationId para el contacto: {contact_id}")
            search_response = await client.get(search_url, headers=headers)
            
            if search_response.status_code == 200:
                conversations = search_response.json().get("conversations", [])
                if conversations:
                    conversation_id = conversations[0].get("id")
                    logger.info(f"ConversationId encontrado: {conversation_id}")

        # Si no se encuentra una conversación, la API debería crear una con el primer mensaje.
        # Usamos el contactId como fallback si no se encuentra un conversationId específico.
        if not conversation_id:
            logger.warning(f"No se encontró conversationId para {contact_id}. Se usará el contactId como fallback.")
            conversation_id = contact_id

        # Paso 2: Enviar el mensaje usando el endpoint general
        url = f"{GHL_API_URL}/conversations/messages"
        payload = {
            "type": "WhatsApp",
            "contactId": contact_id,
            "conversationId": conversation_id,
            "message": message_body,
            "direction": direction
        }

        # LA MAGIA FINAL: Solo añadimos el userId si el mensaje es SALIENTE.
        if direction == "outbound":
            payload["userId"] = user_id
        
        async with httpx.AsyncClient(timeout=GHL_API_TIMEOUT) as client:
            logger.info(f"GHL API Call (add_message): Añadiendo mensaje con payload: {json.dumps(payload)}")
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            logger.info(f"GHL API Response: Mensaje para {contact_id} añadido exitosamente.")
            return True
            
    except httpx.HTTPStatusError as e:
        logger.error(f"Error HTTP al añadir mensaje en GHL. Status: {e.response.status_code}. Response: {e.response.text}")
        return False
    except Exception as e:
        logger.error(f"Excepción inesperada al intentar añadir mensaje: {e}", exc_info=True)
        return False