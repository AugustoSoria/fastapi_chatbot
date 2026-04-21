from fastapi import FastAPI
from app.routes import ask_routes
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()    
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)

app.include_router(ask_routes.router, prefix="/ask", tags=["ask"])

@app.get('/')
def read_root():
    return {"Hello": "World"}