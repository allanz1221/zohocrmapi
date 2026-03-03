from fastapi import FastAPI, Request, Form, Depends
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import os
import datetime
from zoho_service import ZohoClient
import logging

# Configuración de logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuración de la Base de Datos
# Usamos /tmp/database.db ya que Vercel solo permite escribir en /tmp
DB_PATH = "/tmp/database.db" if os.getenv("VERCEL") else "database.db"
SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Modelos de la Base de Datos
class WebhookLog(Base):
    __tablename__ = "webhook_logs"
    id = Column(Integer, primary_key=True, index=True)
    payload = Column(Text)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class ContactUpdateLog(Base):
    __tablename__ = "contact_updates"
    id = Column(Integer, primary_key=True, index=True)
    contact_id = Column(String)
    update_data = Column(Text)
    result = Column(Text)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

# Crear tablas si no existen
Base.metadata.create_all(bind=engine)

# Dependencia para obtener la sesión de la DB
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

app = FastAPI(title="Integración Zoho CRM con FastAPI")

# Montar archivos estáticos para el frontend (HTML/CSS)
if not os.path.exists("static"):
    os.makedirs("static")
app.mount("/static", StaticFiles(directory="static"), name="static")

zoho = ZohoClient()

@app.get("/")
async def read_index():
    return FileResponse("static/index.html")

@app.post("/webhook")
async def handle_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Endpoint para recibir webhooks desde Zoho CRM.
    """
    payload = await request.json()
    logger.info(f"Webhook recibido de Zoho: {payload}")
    
    # Guardar en la base de datos
    db_log = WebhookLog(payload=str(payload))
    db.add(db_log)
    db.commit()
    
    return {"status": "success", "message": "Webhook recibido y registrado correctamente"}

@app.post("/update-contact")
async def update_contact(
    contact_id: str = Form(...),
    first_name: str = Form(None),
    last_name: str = Form(None),
    email: str = Form(None),
    phone: str = Form(None),
    db: Session = Depends(get_db)
):
    """
    Endpoint para actualizar un contacto en Zoho CRM desde el formulario web.
    """
    update_data = {}
    if first_name: update_data["First_Name"] = first_name
    if last_name: update_data["Last_Name"] = last_name
    if email: update_data["Email"] = email
    if phone: update_data["Phone"] = phone

    try:
        result = await zoho.update_contact(contact_id, update_data)
        logger.info(f"Resultado de actualización para {contact_id}: {result}")
        
        # Guardar registro en la base de datos
        db_log = ContactUpdateLog(
            contact_id=contact_id,
            update_data=str(update_data),
            result=str(result)
        )
        db.add(db_log)
        db.commit()
        
        return JSONResponse(content={"status": "success", "data": result})
    except Exception as e:
        logger.error(f"Error al actualizar contacto {contact_id}: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": f"Error interno: {str(e)}"}
        )

# Necesario para ejecución local
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
