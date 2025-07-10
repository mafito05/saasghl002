# logger_config.py
import logging
import sys

# Configuración básica del logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(message)s",
    handlers=[
        logging.FileHandler("app.log"), # Escribe en el archivo app.log
        logging.StreamHandler(sys.stdout) # También imprime en la consola
    ]
)

logger = logging.getLogger(__name__)