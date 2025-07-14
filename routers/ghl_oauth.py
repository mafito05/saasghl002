# routers/ghl_oauth.py
import os
import httpx
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from urllib.parse import urlencode
import json

from database.connection import get_db
from models.instance import Instance as InstanceModel
from models.user import User
from routers.auth import get_current_active_user
from logger_config import logger

router = APIRouter(prefix="/marketplace", tags=["Marketplace OAuth"])

GHL_CLIENT_ID = os.getenv("GHL_CLIENT_ID")
GHL_CLIENT_SECRET = os.getenv("GHL_CLIENT_SECRET")
GHL_BASE_URL = "https://marketplace.gohighlevel.com/oauth/chooselocation"
GHL_TOKEN_URL = "https://services.leadconnectorhq.com/oauth/token"
REDIRECT_URI = "http://localhost:8000/api/marketplace/callback"

@router.get("/connect")
async def connect_to_ghl(current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    """
    Paso 1: Redirige al usuario a GoHighLevel para que autorice la aplicación.
    """
    instance = db.query(InstanceModel).filter(InstanceModel.owner_id == current_user.id).first()
    if not instance:
        raise HTTPException(status_code=404, detail="No se encontró una instancia. Por favor, cree una primero.")

    # Usamos los scopes corregidos y validados
    scopes = " ".join([
        "contacts.readonly",
        "contacts.write",
        "conversations.readonly",
        "conversations.write",
        "conversations/message.readonly",
        "conversations/message.write",
        "users.readonly"
    ])
    
    state = f"user:{current_user.id}"
    
    params = {
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "client_id": GHL_CLIENT_ID,
        "scope": scopes,
        "state": state,
    }
    
    authorization_url = f"{GHL_BASE_URL}?{urlencode(params)}"
    logger.info(f"Redirigiendo al usuario a la URL de autorización de GHL: {authorization_url}")
    return RedirectResponse(authorization_url)

@router.get("/callback")
async def ghl_oauth_callback(code: str, state: str, request: Request, db: Session = Depends(get_db)):
    """
    Paso 2: GHL redirige aquí. Intercambiamos el código por tokens y los guardamos.
    """
    logger.info(f"Recibido callback de GHL con código de autorización y estado: {state}")
    
    try:
        user_id_str = state.split(':')[1]
        user_id = int(user_id_str)
    except (IndexError, ValueError):
        raise HTTPException(status_code=400, detail="Parámetro 'state' inválido o malformado.")

    instance = db.query(InstanceModel).filter(InstanceModel.owner_id == user_id).first()
    if not instance:
        raise HTTPException(status_code=400, detail="No se pudo asociar el callback a una instancia existente.")
    
    token_data = {
        "client_id": GHL_CLIENT_ID,
        "client_secret": GHL_CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
    }

    async with httpx.AsyncClient() as client:
        try:
            token_response = await client.post(GHL_TOKEN_URL, data=token_data)
            token_response.raise_for_status()
            
            token_json = token_response.json()
            logger.info("================= RESPUESTA DE GOHIGHLEVEL =================")
            logger.info(f"Datos JSON recibidos de GHL: {json.dumps(token_json, indent=2)}")
            logger.info("==========================================================")
            
            # Guardamos todos los datos necesarios
            instance.ghl_access_token = token_json.get("access_token")
            instance.ghl_refresh_token = token_json.get("refresh_token")
            instance.ghl_location_id = token_json.get("locationId")
            instance.ghl_user_id = token_json.get("userId")
            instance.is_connected = True
            
            db.commit()
            db.refresh(instance)
            
            logger.info("Datos guardados en la base de datos.")
            logger.info(f"Verificación post-guardado -> Access Token: {'OK' if instance.ghl_access_token else 'FALTANTE'}")
            logger.info(f"Verificación post-guardado -> Location ID: {instance.ghl_location_id}")
            logger.info(f"Verificación post-guardado -> User ID: {instance.ghl_user_id}")

            return {"status": "success", "message": "GoHighLevel ha sido conectado exitosamente. Ya puedes cerrar esta ventana."}

        except httpx.HTTPStatusError as e:
            logger.error(f"Error al intercambiar el código por tokens: {e.response.text}")
            raise HTTPException(status_code=400, detail=f"Error al comunicarse con GHL: {e.response.text}")
        except Exception as e:
            # Captura cualquier otro error inesperado (como un JSON malformado)
            logger.error(f"Excepción no controlada en el callback de GHL: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Ocurrió un error interno al procesar la respuesta de GHL.")