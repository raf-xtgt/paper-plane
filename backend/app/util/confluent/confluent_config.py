from dotenv import load_dotenv
import os
from confluent_kafka import Producer

load_dotenv()

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS")
KAFKA_API_KEY = os.getenv("KAFKA_API_KEY")
KAFKA_API_SECRET = os.getenv("KAFKA_API_SECRET")

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