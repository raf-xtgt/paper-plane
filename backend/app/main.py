from fastapi import FastAPI
from dotenv import load_dotenv
import os
from fastapi.middleware.cors import CORSMiddleware
import vertexai

import asyncio
import json
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Form, Request, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from confluent_kafka import Producer, Consumer, KafkaError
from twilio.rest import Client
from pydantic import BaseModel

load_dotenv()

GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID")
GCP_REGION = os.getenv("GCP_REGION") # e.g., "us-central1"
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS")
KAFKA_API_KEY = os.getenv("KAFKA_API_KEY")
KAFKA_API_SECRET = os.getenv("KAFKA_API_SECRET")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_NUMBER = os.getenv("TWILIO_NUMBER")

# Topics
TOPIC_INBOUND = "whatsapp_inbound"
TOPIC_OUTBOUND = "whatsapp_outbound"

# --- Kafka Setup ---
conf_base = {
    'bootstrap.servers': KAFKA_BOOTSTRAP_SERVERS,
    'security.protocol': 'SASL_SSL',
    'sasl.mechanism': 'PLAIN',
    'sasl.username': KAFKA_API_KEY,
    'sasl.password': KAFKA_API_SECRET,
}

# Producer
producer = Producer(conf_base)

# Twilio Client
twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

if not GCP_PROJECT_ID or not GCP_REGION:
    raise EnvironmentError("GCP_PROJECT_ID and GCP_REGION environment variables must be set.")

vertexai.init(project=GCP_PROJECT_ID, location=GCP_REGION)

# --- Models ---
class OutboundMessage(BaseModel):
    to_number: str  # Format: whatsapp:+123456789
    message_body: str

# --- Kafka Helpers ---
def delivery_report(err, msg):
    """ Called once for each message produced to indicate delivery result. """
    if err is not None:
        print(f'Message delivery failed: {err}')
    else:
        print(f'Message delivered to {msg.topic()} [{msg.partition()}]')

def produce_event(topic: str, data: dict):
    """Sends data to Confluent Kafka"""
    try:
        producer.produce(
            topic, 
            json.dumps(data).encode('utf-8'), 
            callback=delivery_report
        )
        producer.poll(0) # Trigger callbacks
    except Exception as e:
        print(f"Error producing to Kafka: {e}")

# --- Background Consumers ---

async def consume_inbound():
    """
    Listens to 'whatsapp_inbound'.
    Requirement: Print message to FastAPI console.
    """
    c_conf = conf_base.copy()
    c_conf.update({
        'group.id': 'fastapi_inbound_printer_group',
        'auto.offset.reset': 'earliest'
    })
    consumer = Consumer(c_conf)
    consumer.subscribe([TOPIC_INBOUND])

    print("Listening to Inbound Topic...")
    try:
        while True:
            msg = consumer.poll(1.0)
            if msg is None: 
                await asyncio.sleep(0.1)
                continue
            if msg.error():
                print(f"Consumer error: {msg.error()}")
                continue
            
            # Process message
            data = json.loads(msg.value().decode('utf-8'))
            print(f"\n[INBOUND EVENT RECEIVED]: From {data.get('from')}: {data.get('body')}\n")
            
            await asyncio.sleep(0.01) # Yield control
    finally:
        consumer.close()

async def consume_outbound():
    """
    Listens to 'whatsapp_outbound'.
    Requirement: Forward event to Business Client via Twilio.
    """
    c_conf = conf_base.copy()
    c_conf.update({
        'group.id': 'fastapi_outbound_sender_group',
        'auto.offset.reset': 'earliest'
    })
    consumer = Consumer(c_conf)
    consumer.subscribe([TOPIC_OUTBOUND])

    print("Listening to Outbound Topic...")
    try:
        while True:
            msg = consumer.poll(1.0)
            if msg is None: 
                await asyncio.sleep(0.1)
                continue
            if msg.error():
                print(f"Consumer error: {msg.error()}")
                continue
            
            # Process message
            data = json.loads(msg.value().decode('utf-8'))
            target_number = data.get('to')
            body = data.get('body')
            
            print(f"Processing Outbound: Sending '{body}' to {target_number} via Twilio...")
            
            try:
                message = twilio_client.messages.create(
                    from_=TWILIO_NUMBER,
                    body=body,
                    to=target_number
                )
                print(f"Twilio Sent SID: {message.sid}")
            except Exception as e:
                print(f"Failed to send via Twilio: {e}")

            await asyncio.sleep(0.01)
    finally:
        consumer.close()


# --- Lifecycle Manager ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start Consumers in background tasks
    task_in = asyncio.create_task(consume_inbound())
    task_out = asyncio.create_task(consume_outbound())
    yield
    # Clean up tasks (simplified for this snippet)
    task_in.cancel()
    task_out.cancel()

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

# --- Routes ---

@app.post("/webhook/twilio")
async def twilio_webhook(request: Request):
    """
    1. Receives incoming webhook from Twilio (Client sent message).
    2. Produces event to 'whatsapp_inbound'.
    """
    # Twilio sends form data, not JSON
    form_data = await request.form()
    
    message_body = form_data.get('Body', '')
    from_number = form_data.get('From', '')
    
    event_data = {
        "from": from_number,
        "body": message_body,
        "raw_data": str(form_data)
    }
    
    # Produce to Kafka
    produce_event(TOPIC_INBOUND, event_data)
    
    return {"status": "received", "topic": TOPIC_INBOUND}

@app.post("/api/send-message")
async def send_message_api(payload: OutboundMessage):
    """
    1. API receives request to send message.
    2. Produces event to 'whatsapp_outbound'.
    (The background consumer will pick this up and call Twilio).
    """
    event_data = {
        "to": payload.to_number,
        "body": payload.message_body
    }
    
    produce_event(TOPIC_OUTBOUND, event_data)
    
    return {"status": "queued", "topic": TOPIC_OUTBOUND}

@app.get("/")
def read_root():
    return {"message": "Omnichannel API Running"}

