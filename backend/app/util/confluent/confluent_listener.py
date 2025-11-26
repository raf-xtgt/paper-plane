import json
from app.util.confluent.confluent_config import *
from app.util.confluent.confluent_helper import *
from confluent_kafka import Consumer, KafkaError
from app.util.twilio.twilio_config import *
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