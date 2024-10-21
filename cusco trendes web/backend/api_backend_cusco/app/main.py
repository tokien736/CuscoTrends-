from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from datetime import timedelta, datetime
from jose import JWTError, jwt

from .database import get_db, Base, engine  # Importar correctamente get_db
from .models import Usuario
from .schemas import UsuarioCreate, Token

# Crear la base de datos
Base.metadata.create_all(bind=engine)

# Configurar la aplicación FastAPI
app = FastAPI()

# Configurar CORS
origins = [
    "http://localhost:5173",  # Cambia el puerto si es necesario
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuración de seguridad
SECRET_KEY = "secretkey123456"  # Cambia esto en producción
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Función para crear un usuario por defecto
def crear_usuario_por_defecto(db: Session):
    usuario = db.query(Usuario).filter(Usuario.email == "admin@admin.com").first()
    if not usuario:
        hashed_password = pwd_context.hash("admin")
        admin_user = Usuario(nombre="admin", email="admin@admin.com", password=hashed_password)
        db.add(admin_user)
        db.commit()
        db.refresh(admin_user)
        print("Usuario admin@admin.com creado con éxito")
    else:
        print("El usuario admin@admin.com ya existe")

# Evento que se ejecuta cuando la aplicación se inicia
@app.on_event("startup")
def startup():
    db = next(get_db())  # Obtener la sesión de la base de datos
    crear_usuario_por_defecto(db)

# Ruta para crear un nuevo usuario
@app.post("/register/")
async def create_user(user: UsuarioCreate, db: Session = Depends(get_db)):
    hashed_password = pwd_context.hash(user.password)
    db_user = Usuario(nombre=user.nombre, email=user.email, password=hashed_password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return {"msg": "User created successfully"}

# Función para autenticar usuario
def authenticate_user(db: Session, email: str, password: str):
    user = db.query(Usuario).filter(Usuario.email == email).first()
    if not user:
        return False
    if not pwd_context.verify(password, user.password):
        return False
    return user

# Función para crear un token de acceso
def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# Ruta para obtener el token
@app.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

# Ruta para verificar el token
@app.get("/users/me")
async def read_users_me(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = db.query(Usuario).filter(Usuario.email == email).first()
    if user is None:
        raise credentials_exception
    return user
