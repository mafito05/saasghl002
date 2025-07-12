# services/gohighlevel_service.py
import os
import httpx
from typing import Optional, Dict, Any
from logger_config import logger

GHL_API_URL = "https://services.leadconnectorhq.com"

async def _get_headers(access_token: str) -> Dict[str, str]:
    """Construye los encabezados de autenticación para GHL."""
    if not access_token:
        raise ValueError("Se requiere un access_token de GHL para hacer la petición.")
    return {
        "Authorization": f"Bearer {access_token}",
        "Version": "2021-07-28",
        "Accept": "application/json",
    }

async def search_contact_by_phone(phone: str, access_token: str) -> Optional[Dict[str, Any]]:
    """
    Busca un contacto en GoHighLevel por su número de teléfono usando un token OAuth.
    """
    headers = await _get_headers(access_token)
    params = {"query": phone}
    
    async with httpx.AsyncClient() as client:
        try:
            logger.info(f"GHL API Call: Buscando contacto con teléfono {phone}")
            response = await client.get(f"{GHL_API_URL}/contacts/lookup", headers=headers, params=params)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("contacts") and len(data["contacts"]) > 0:
                    contact = data["contacts"][0]
                    logger.info(f"GHL API Response: Contacto encontrado, ID: {contact.get('id')}")
                    return contact
                else:
                    logger.info("GHL API Response: No se encontró ningún contacto.")
                    return None
            else:
                logger.error(f"Error al buscar contacto en GHL ({response.status_code}): {response.text}")
                return None
        except Exception as e:
            logger.error(f"Excepción en la llamada a la API de GHL (search_contact): {e}", exc_info=True)
            return None

async def create_contact_in_ghl(phone: str, name: str, location_id: str, access_token: str) -> Optional[Dict[str, Any]]:
    """
    Crea un nuevo contacto en GoHighLevel usando un token OAuth.
    """
    headers = await _get_headers(access_token)
    headers["Content-Type"] = "application/json"
    
    payload = {
        "name": name,
        "phone": phone,
        "locationId": location_id, # Es importante especificar la ubicación
        "source": "WhatsApp SaaS Integration"
    }
    
    async with httpx.AsyncClient() as client:
        try:
            logger.info(f"GHL API Call: Creando contacto para {phone} en location {location_id}")
            response = await client.post(f"{GHL_API_URL}/contacts/", headers=headers, json=payload)
            
            if response.status_code in [200, 201]:
                contact_data = response.json().get("contact")
                logger.info(f"GHL API Response: Contacto creado, ID: {contact_data.get('id')}")
                return contact_data
            else:
                logger.error(f"Error al crear contacto en GHL ({response.status_code}): {response.text}")
                return None
        except Exception as e:
            logger.error(f"Excepción en la llamada a la API de GHL (create_contact): {e}", exc_info=True)
            return None

async def add_inbound_message_to_ghl(contact_id: str, message_body: str, access_token: str) -> bool:
    """
    Añade un mensaje entrante a la conversación de un contacto en GoHighLevel.
    """
    headers = await _get_headers(access_token)
    headers["Content-Type"] = "application/json"

    payload = {
        "type": "SMS",
        "message": message_body,
    }
    
    url = f"{GHL_API_URL}/conversations/messages/contact/{contact_id}"
    
    async with httpx.AsyncClient() as client:
        try:
            logger.info(f"GHL API Call: Añadiendo mensaje al contacto {contact_id}")
            response = await client.post(url, headers=headers, json=payload)
            
            if response.status_code in [200, 201]:
                logger.info("GHL API Response: Mensaje añadido exitosamente.")
                return True
            else:
                logger.error(f"Error al añadir mensaje en GHL ({response.status_code}): {response.text}")
                return False
        except Exception as e:
            logger.error(f"Excepción en la llamada a la API de GHL (add_inbound_message): {e}", exc_info=True)
            return False