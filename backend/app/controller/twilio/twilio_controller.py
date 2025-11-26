from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
import uuid
from app.model.outbound_message_model import *
from app.util.confluent import *

router = APIRouter(
    prefix="/twilio",  
    tags=["Session"]   
)

@router.post("/webhook")
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
    print("msg from whatsapp", message_body)
    return {"status": "received", "topic": TOPIC_INBOUND}

@router.post("/send-message")
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