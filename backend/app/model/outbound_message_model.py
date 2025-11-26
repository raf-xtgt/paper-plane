
from pydantic import BaseModel

class OutboundMessage(BaseModel):
    to_number: str  # Format: whatsapp:+123456789
    message_body: str