# routers/webhook.py
from fastapi import APIRouter, Request, Response, status
import json
from logger_config import logger # Importamos nuestro logger

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])

@router.post("/evolution/{instance_name}")
async def evolution_webhook(instance_name: str, request: Request):
    """
    Recibe todas las notificaciones de las instancias de Evolution API.
    """
    try:
        data = await request.json()

        # Usamos el logger en lugar de print()
        logger.info(f"Webhook recibido de la instancia '{instance_name}':")
        logger.info(json.dumps(data, indent=2))

        # Aquí, en el futuro, irá la lógica para enviar a GHL y n8n

    except json.JSONDecodeError:
        logger.error("Se recibió un webhook con cuerpo no-JSON.")

    return Response(status_code=status.HTTP_200_OK)