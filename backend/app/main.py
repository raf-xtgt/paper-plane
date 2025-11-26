from dotenv import load_dotenv
import os
from fastapi.middleware.cors import CORSMiddleware
import vertexai
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.util.confluent import *
from app.controller import twilio


load_dotenv()

GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID")
GCP_REGION = os.getenv("GCP_REGION") # e.g., "us-central1"

if not GCP_PROJECT_ID or not GCP_REGION:
    raise EnvironmentError("GCP_PROJECT_ID and GCP_REGION environment variables must be set.")

vertexai.init(project=GCP_PROJECT_ID, location=GCP_REGION)



# --- Lifecycle Manager ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start Consumers in background tasks
    task_in = asyncio.create_task(consume_inbound())
    task_out = asyncio.create_task(consume_outbound())
    
    yield
    
    # Clean up tasks on shutdown
    task_in.cancel()
    task_out.cancel()
    
    # Wait for tasks to complete cancellation
    try:
        await task_in
    except asyncio.CancelledError:
        pass
    
    try:
        await task_out
    except asyncio.CancelledError:
        pass

app = FastAPI(title="Omni Channel Service", lifespan=lifespan)

# --- Middlewares ---
origins = ["http://localhost:3000"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

url_prefix = "/api/ppl"
app.include_router(twilio.router, prefix=url_prefix)



@app.get("/")
def read_root():
    return {"message": "Omnichannel API Running"}

