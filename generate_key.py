# generate_key.py
from cryptography.fernet import Fernet

# Genera una nueva clave segura
key = Fernet.generate_key()

# Imprime la clave en la consola para que la puedas copiar
print("Copia y pega esta clave en tu archivo .env como FIELD_ENCRYPTION_KEY:")
print(key.decode())