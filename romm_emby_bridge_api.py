
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, FileResponse
import httpx
import json
from typing import List, Dict, Any
from datetime import datetime
import os

app = FastAPI(title="RomM-Emby Bridge API", version="1.0.0")

# Configuration
ROMM_BASE_URL = "http://romm:8080"  # URL interne du container romm
ROMM_API_KEY = ""  # À configurer si romm nécessite une authentification

class RommEmbyBridge:
    def __init__(self):
        self.romm_url = ROMM_BASE_URL
        self.headers = {"Authorization": f"Bearer {ROMM_API_KEY}"} if ROMM_API_KEY else {}

    async def get_romm_games(self) -> List[Dict]:
        """Récupère la liste des jeux depuis romm.app"""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(f"{self.romm_url}/api/roms", headers=self.headers)
                response.raise_for_status()
                return response.json()
            except Exception as e:
                print(f"Erreur lors de la récupération des jeux: {e}")
                return []

    async def get_game_details(self, game_id: int) -> Dict:
        """Récupère les détails d'un jeu spécifique"""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(f"{self.romm_url}/api/roms/{game_id}", headers=self.headers)
                response.raise_for_status()
                return response.json()
            except Exception as e:
                print(f"Erreur lors de la récupération du jeu {game_id}: {e}")
                return {}

    def convert_to_emby_format(self, romm_games: List[Dict]) -> Dict:
        """Convertit les données romm.app au format Emby"""
        emby_items = []

        for game in romm_games:
            emby_item = {
                "Id": str(game.get("id", "")),
                "Name": game.get("name", ""),
                "Overview": game.get("summary", ""),
                "ProductionYear": game.get("release_date", "")[:4] if game.get("release_date") else None,
                "Genres": [game.get("platform_name", "")] if game.get("platform_name") else [],
                "Type": "Game",
                "MediaType": "Game",
                "RunTimeTicks": 0,
                "IsFolder": False,
                "ParentId": "",
                "UserData": {
                    "PlaybackPositionTicks": 0,
                    "PlayCount": 0,
                    "IsFavorite": False,
                    "Played": False
                },
                "PrimaryImageAspectRatio": 1.0,
                "ImageTags": {
                    "Primary": f"romm_cover_{game.get('id', '')}"
                },
                "BackdropImageTags": [],
                "LocationType": "FileSystem",
                "MediaSources": [{
                    "Id": str(game.get("id", "")),
                    "Path": f"/api/games/{game.get('id', '')}/launch",
                    "Type": "Default"
                }],
                "Platform": game.get("platform_name", ""),
                "ReleaseDate": game.get("release_date", ""),
                "GameSystem": game.get("platform_name", "")
            }
            emby_items.append(emby_item)

        return {
            "Items": emby_items,
            "TotalRecordCount": len(emby_items)
        }

bridge = RommEmbyBridge()

@app.get("/")
async def root():
    return {"message": "RomM-Emby Bridge API", "version": "1.0.0"}

@app.get("/api/games")
async def get_games():
    """Endpoint compatible Emby pour récupérer la liste des jeux"""
    try:
        romm_games = await bridge.get_romm_games()
        emby_format = bridge.convert_to_emby_format(romm_games)
        return JSONResponse(content=emby_format)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")

@app.get("/api/games/{game_id}")
async def get_game(game_id: int):
    """Récupère les détails d'un jeu spécifique"""
    try:
        game_details = await bridge.get_game_details(game_id)
        if not game_details:
            raise HTTPException(status_code=404, detail="Jeu non trouvé")

        emby_format = bridge.convert_to_emby_format([game_details])
        return JSONResponse(content=emby_format["Items"][0] if emby_format["Items"] else {})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")

@app.get("/api/games/{game_id}/cover")
async def get_game_cover(game_id: int):
    """Proxy pour récupérer la jaquette d'un jeu"""
    async with httpx.AsyncClient() as client:
        try:
            # Récupère la jaquette depuis romm.app
            response = await client.get(f"{ROMM_BASE_URL}/api/roms/{game_id}/cover")
            if response.status_code == 200:
                return FileResponse(
                    content=response.content,
                    media_type=response.headers.get("content-type", "image/jpeg"),
                    filename=f"cover_{game_id}.jpg"
                )
            else:
                raise HTTPException(status_code=404, detail="Jaquette non trouvée")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")

@app.post("/api/games/{game_id}/launch")
async def launch_game(game_id: int):
    """Lance un jeu via romm.app"""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(f"{ROMM_BASE_URL}/api/roms/{game_id}/launch", headers=bridge.headers)
            if response.status_code == 200:
                return {"message": f"Jeu {game_id} lancé avec succès", "status": "success"}
            else:
                raise HTTPException(status_code=400, detail="Impossible de lancer le jeu")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")

@app.get("/api/platforms")
async def get_platforms():
    """Récupère la liste des plateformes/consoles"""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{ROMM_BASE_URL}/api/platforms", headers=bridge.headers)
            response.raise_for_status()
            platforms = response.json()

            # Format compatible Emby
            emby_platforms = []
            for platform in platforms:
                emby_platforms.append({
                    "Id": str(platform.get("id", "")),
                    "Name": platform.get("name", ""),
                    "Type": "GameSystem"
                })

            return {"Items": emby_platforms}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")

# Health check
@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
