FROM python:3.11-slim

WORKDIR /app

# Installation des dépendances
RUN pip install fastapi uvicorn httpx

# Copie du code de l'API
COPY romm_emby_bridge_api.py /app/

# Exposition du port
EXPOSE 8000

# Commande de démarrage
CMD ["python", "romm_emby_bridge_api.py"]
