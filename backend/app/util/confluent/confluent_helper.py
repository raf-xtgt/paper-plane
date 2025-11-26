import json
from app.util.confluent.confluent_config import producer

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