from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database.database import engine,Base
from routers.auth import auth
from routers.posts import posts
from routers.profile import profile

Base.metadata.create_all(bind=engine) #Create tables in supabase
app = FastAPI()
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Hello from Backend!"}



app.include_router(auth.router,prefix="/auth",tags=["Authentication"])    
app.include_router(posts.router, prefix="/posts", tags=["Posts"])
app.include_router(profile.router,prefix="/profile",tags=["Profile"])









