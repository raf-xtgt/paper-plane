from dotenv import load_dotenv
import os
import logging
from fastapi.middleware.cors import CORSMiddleware
import vertexai
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.util.confluent import *
from app.util.confluent.lead_gen_listener import lead_gen_listener
from app.controller import twilio
from app.controller import agents


load_dotenv()

# Configure logging for lead generation pipeline
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Set specific log levels for lead generation components
logging.getLogger("lead_gen_pipeline").setLevel(logging.INFO)
logging.getLogger("lead_gen_pipeline.scout").setLevel(logging.INFO)
logging.getLogger("lead_gen_pipeline.researcher").setLevel(logging.INFO)
logging.getLogger("lead_gen_pipeline.strategist").setLevel(logging.INFO)
logging.getLogger("lead_gen_controller").setLevel(logging.INFO)

# Optionally set DEBUG level for development (can be controlled via env var)
if os.getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
    logging.getLogger("lead_gen_pipeline").setLevel(logging.DEBUG)
    logging.getLogger("lead_gen_pipeline.scout").setLevel(logging.DEBUG)
    logging.getLogger("lead_gen_pipeline.researcher").setLevel(logging.DEBUG)
    logging.getLogger("lead_gen_pipeline.strategist").setLevel(logging.DEBUG)
    logging.getLogger("lead_gen_controller").setLevel(logging.DEBUG)

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
    task_lead_gen = asyncio.create_task(lead_gen_listener.start())
    
    yield
    
    # Clean up tasks on shutdown
    task_in.cancel()
    task_out.cancel()
    task_lead_gen.cancel()
    
    # Wait for tasks to complete cancellation
    try:
        await task_in
    except asyncio.CancelledError:
        pass
    
    try:
        await task_out
    except asyncio.CancelledError:
        pass
    
    try:
        await task_lead_gen
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
app.include_router(agents.router, prefix=url_prefix)



@app.get("/")
def read_root():
    return {"message": "Omnichannel API Running"}

