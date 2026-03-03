from fastapi import FastAPI, Request, Form, Depends, HTTPException
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

class Prospecto(Base):
    __tablename__ = "prospectos"
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String)
    apellido = Column(String)
    email = Column(String, unique=True)
    telefono = Column(String)
    empresa = Column(String)
    estado = Column(String, default="Nuevo")
    creado_en = Column(DateTime, default=datetime.datetime.utcnow)

# Crear tablas
Base.metadata.create_all(bind=engine)

# Dependencia
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

app = FastAPI(title="Integración Zoho CRM & CRM Local")

# Montar archivos estáticos
if not os.path.exists("static"):
    os.makedirs("static")
app.mount("/static", StaticFiles(directory="static"), name="static")

zoho = ZohoClient()

@app.get("/")
async def read_index():
    return FileResponse("static/index.html")

# --- Endpoints de Zoho ---

@app.post("/webhook")
async def handle_webhook(request: Request, db: Session = Depends(get_db)):
    payload = await request.json()
    logger.info(f"Webhook recibido: {payload}")
    db_log = WebhookLog(payload=str(payload))
    db.add(db_log)
    db.commit()
    return {"status": "success", "message": "Webhook registrado"}

@app.post("/update-contact")
async def update_contact(
    contact_id: str = Form(...),
    first_name: str = Form(None),
    last_name: str = Form(None),
    email: str = Form(None),
    phone: str = Form(None),
    db: Session = Depends(get_db)
):
    update_data = {}
    if first_name: update_data["First_Name"] = first_name
    if last_name: update_data["Last_Name"] = last_name
    if email: update_data["Email"] = email
    if phone: update_data["Phone"] = phone

    try:
        result = await zoho.update_contact(contact_id, update_data)
        db_log = ContactUpdateLog(contact_id=contact_id, update_data=str(update_data), result=str(result))
        db.add(db_log)
        db.commit()
        return JSONResponse(content={"status": "success", "data": result})
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})

# --- Endpoints CRUD de Prospectos (Local) ---

@app.get("/prospectos")
async def listar_prospectos(db: Session = Depends(get_db)):
    return db.query(Prospecto).all()

@app.post("/prospectos")
async def crear_prospecto(
    nombre: str = Form(...),
    apellido: str = Form(...),
    email: str = Form(...),
    telefono: str = Form(None),
    empresa: str = Form(None),
    db: Session = Depends(get_db)
):
    prospecto = Prospecto(nombre=nombre, apellido=apellido, email=email, telefono=telefono, empresa=empresa)
    db.add(prospecto)
    try:
        db.commit()
        db.refresh(prospecto)
        return prospecto
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail="El email ya existe o error en datos")

@app.delete("/prospectos/{id}")
async def borrar_prospecto(id: int, db: Session = Depends(get_db)):
    prospecto = db.query(Prospecto).filter(Prospecto.id == id).first()
    if not prospecto:
        raise HTTPException(status_code=404, detail="Prospecto no encontrado")
    db.delete(prospecto)
    db.commit()
    return {"status": "success", "message": "Prospecto eliminado"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
