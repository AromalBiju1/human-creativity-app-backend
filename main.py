from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database.database import engine,Base
from routers.auth import auth
from routers.posts import posts
from routers.profile import profile
from routers.follow import follow
from routers.chat import router as chat_router      
from routers.chat.manager import manager            
from contextlib import asynccontextmanager

Base.metadata.create_all(bind=engine) #Create tables in supabase


@asynccontextmanager
async def lifespan(app: FastAPI):
    await manager.startup()    # 🔴 Connect to Redis when app starts
    yield
    await manager.shutdown()   # 🔴 Close Redis when app stops


app = FastAPI(lifespan=lifespan)


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
app.include_router(follow.router,prefix="/follow",tags=["Follow"])
app.include_router(chat_router,prefix="/chat",tags=["Chat"])        








