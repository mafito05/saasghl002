import httpx
from typing import Optional, Dict, Any
from logger_config import logger

GHL_API_URL = "https://services.leadconnectorhq.com"

async def search_contact_by_phone(phone: str, ghl_api_key: str) -> Optional[Dict[str, Any]]:
    """Busca un contacto en GoHighLevel por su número de teléfono usando la clave proporcionada."""
    if not ghl_api_key:
        logger.error("Intento de buscar contacto sin una GHL API Key.")
        return None
        
    headers = {
        "Authorization": f"Bearer {ghl_api_key}",
        "Version": "2021-07-28",
        "Accept": "application/json"
    }
    params = {"query": phone}
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{GHL_API_URL}/contacts/lookup", headers=headers, params=params)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("contacts") and len(data["contacts"]) > 0:
                    contact = data["contacts"][0]
                    logger.info(f"Contacto encontrado en GHL: ID {contact.get('id')}")
                    return contact
                else:
                    logger.info(f"No se encontró ningún contacto en GHL con el teléfono {phone}.")
                    return None
            else:
                logger.error(f"Error al buscar contacto en GHL ({response.status_code}): {response.text}")
                return None
        except httpx.RequestError as e:
            logger.error(f"Error de red al buscar contacto en GHL: {e}")
            return None

async def create_contact_in_ghl(phone: str, name: str, ghl_api_key: str) -> Optional[Dict[str, Any]]:
    """Crea un nuevo contacto en GoHighLevel usando la clave proporcionada."""
    if not ghl_api_key:
        logger.error("Intento de crear contacto sin una GHL API Key.")
        return None

    headers = {
        "Authorization": f"Bearer {ghl_api_key}",
        "Version": "2021-07-28",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    payload = {
        "name": name,
        "phone": phone,
        "source": "WhatsApp SaaS Integration"
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(f"{GHL_API_URL}/contacts/", headers=headers, json=payload)
            
            if response.status_code in [200, 201]:
                contact_data = response.json().get("contact")
                logger.info(f"Contacto creado exitosamente en GHL: ID {contact_data.get('id')}")
                return contact_data
            else:
                logger.error(f"Error al crear contacto en GHL ({response.status_code}): {response.text}")
                return None
        except httpx.RequestError as e:
            logger.error(f"Error de red al crear contacto en GHL: {e}")
            return None

async def add_inbound_message_to_ghl(contact_id: str, message_body: str, ghl_api_key: str) -> bool:
    """Añade un mensaje entrante a una conversación en GHL usando la clave proporcionada."""
    if not ghl_api_key:
        logger.error("Intento de añadir mensaje sin una GHL API Key.")
        return False

    headers = {
        "Authorization": f"Bearer {ghl_api_key}",
        "Version": "2021-07-28",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    payload = {
        "type": "SMS", # GHL trata los mensajes de WhatsApp como SMS a través de la API
        "message": message_body,
        "direction": "inbound"
    }
    
    url = f"{GHL_API_URL}/conversations/messages/contact/{contact_id}"
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, headers=headers, json=payload)
            
            if response.status_code in [200, 201]:
                logger.info(f"Mensaje entrante añadido a la conversación del contacto {contact_id} en GHL.")
                return True
            else:
                logger.error(f"Error al añadir mensaje en GHL ({response.status_code}): {response.text}")
                return False
        except httpx.RequestError as e:
            logger.error(f"Error de red al añadir mensaje en GHL: {e}")
            return False