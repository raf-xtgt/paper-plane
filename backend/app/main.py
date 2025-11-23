from fastapi import FastAPI
from dotenv import load_dotenv
import os
from fastapi.middleware.cors import CORSMiddleware
import vertexai


load_dotenv()

GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID")
GCP_REGION = os.getenv("GCP_REGION") # e.g., "us-central1"

if not GCP_PROJECT_ID or not GCP_REGION:
    raise EnvironmentError("GCP_PROJECT_ID and GCP_REGION environment variables must be set.")

vertexai.init(project=GCP_PROJECT_ID, location=GCP_REGION)

app = FastAPI(
    title="Modular Web Service",
    description="An example app using FastAPI APIRoutiners (like Flask Blueprints)",
    version="1.0.0"
)

origins = [
    "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


url_prefix = "/ps"


