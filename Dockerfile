# Dockerfile
FROM python:3.10-slim

WORKDIR /app

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Instalar Docker CLI dentro de la imagen para que pueda comunicarse con el socket de Docker
RUN curl -fsSL https://get.docker.com -o get-docker.sh && sh get-docker.sh

# Copiar el archivo de requerimientos e instalar las librerías de Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el resto del código de tu aplicación
COPY . .

# Exponer el puerto que usará uvicorn
EXPOSE 8000

# Comando para iniciar la aplicación
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]