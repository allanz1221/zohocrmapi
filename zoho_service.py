import httpx
import os
from dotenv import load_dotenv

load_dotenv()

class ZohoClient:
    def __init__(self):
        self.client_id = os.getenv("ZOHO_CLIENT_ID")
        self.client_secret = os.getenv("ZOHO_CLIENT_SECRET")
        self.refresh_token = os.getenv("ZOHO_REFRESH_TOKEN")
        self.data_center = os.getenv("ZOHO_DATA_CENTER", "com")
        self.base_url = f"https://www.zohoapis.{self.data_center}/crm/v2.1"
        self.auth_url = f"https://accounts.zoho.{self.data_center}/oauth/v2/token"
        self.access_token = None

    async def get_access_token(self):
        """
        Obtiene un nuevo token de acceso usando el refresh token.
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.auth_url,
                params={
                    "refresh_token": self.refresh_token,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "grant_type": "refresh_token"
                }
            )
            data = response.json()
            if "access_token" in data:
                self.access_token = data["access_token"]
                return self.access_token
            else:
                raise Exception(f"Error al refrescar el token: {data}")

    async def update_contact(self, contact_id, data):
        """
        Actualiza un contacto en Zoho CRM.
        """
        if not self.access_token:
            await self.get_access_token()

        headers = {
            "Authorization": f"Zoho-oauthtoken {self.access_token}",
            "Content-Type": "application/json"
        }

        # Estructura requerida por la API de Zoho
        payload = {
            "data": [data]
        }

        async with httpx.AsyncClient() as client:
            response = await client.put(
                f"{self.base_url}/Contacts/{contact_id}",
                headers=headers,
                json=payload
            )
            return response.json()
