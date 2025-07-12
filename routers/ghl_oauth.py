# routers/ghl_oauth.py
import os
import httpx
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from urllib.parse import urlencode

from database.connection import get_db
from models.instance import Instance as InstanceModel
from models.user import User
from routers.auth import get_current_active_user
from logger_config import logger

# El prefijo base para todas las rutas de este archivo será /marketplace
router = APIRouter(prefix="/marketplace", tags=["Marketplace OAuth"])

GHL_CLIENT_ID = os.getenv("GHL_CLIENT_ID")
GHL_CLIENT_SECRET = os.getenv("GHL_CLIENT_SECRET")
GHL_BASE_URL = "https://marketplace.gohighlevel.com/oauth/chooselocation"
GHL_TOKEN_URL = "https://services.leadconnectorhq.com/oauth/token"

# Esta es la URL que debes poner en tu App de GHL
REDIRECT_URI = "http://localhost:8000/api/marketplace/callback"

@router.get("/connect")
async def connect_to_ghl(current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    """
    Paso 1: Redirige al usuario a GoHighLevel para que autorice la aplicación.
    """
    instance = db.query(InstanceModel).filter(InstanceModel.owner_id == current_user.id).first()
    if not instance:
        raise HTTPException(status_code=404, detail="No se encontró una instancia. Por favor, cree una primero.")

    scopes = " ".join([
        "contacts.readonly", "contacts.write",
        "conversations.readonly", "conversations.write",
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
    Paso 2: GHL redirige aquí después de la autorización.
    Intercambiamos el código por tokens de acceso y los guardamos.
    """
    logger.info(f"Recibido callback de GHL con el código de autorización y el estado: {state}")
    
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
            logger.info(f"Tokens recibidos de GHL exitosamente: {token_json}")
            
            instance.ghl_access_token = token_json.get("access_token")
            instance.ghl_refresh_token = token_json.get("refresh_token")
            instance.ghl_location_id = token_json.get("locationId")
            instance.is_connected = True
            
            db.commit()
            logger.info(f"Tokens guardados para la instancia '{instance.instance_name}' y la ubicación '{instance.ghl_location_id}'.")

            return {"status": "success", "message": "GoHighLevel ha sido conectado exitosamente. Ya puedes cerrar esta ventana."}

        except httpx.HTTPStatusError as e:
            logger.error(f"Error al intercambiar el código por tokens: {e.response.text}")
            raise HTTPException(status_code=400, detail=f"Error al comunicarse con GHL: {e.response.text}")
