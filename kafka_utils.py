"""
Kafka client utilities for the Notion-py application.
"""
from kafka import KafkaProducer, KafkaConsumer
import json
import threading
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get Kafka bootstrap servers from environment variable or use default
# In Docker container, this should be 'kafka:9092' as set in docker-compose.yml
# For local development outside containers, it should be 'localhost:9092'
KAFKA_BOOTSTRAP_SERVERS = os.environ.get('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')

# Set to True to enable more verbose debug logging
DEBUG_MODE = os.environ.get('KAFKA_DEBUG', 'false').lower() == 'true'

class KafkaClient:
    def __init__(self, bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS):
        self.bootstrap_servers = bootstrap_servers
        self.producer = None
        self._init_producer()
        
    def _init_producer(self):
        try:
            # Use a short timeout to avoid hanging if Kafka is not available
            self.producer = KafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                key_serializer=lambda k: str(k).encode('utf-8') if k else None,
                request_timeout_ms=5000,  # 5 seconds timeout
                connections_max_idle_ms=10000,  # 10 seconds idle timeout
                reconnect_backoff_ms=1000,  # 1 second backoff
                reconnect_backoff_max_ms=5000  # 5 seconds max backoff
            )
            logger.info(f"Kafka producer initialized with bootstrap servers: {self.bootstrap_servers}")
        except Exception as e:
            logger.error(f"Failed to initialize Kafka producer: {e}")
            self.producer = None
    
    def send_message(self, topic, value, key=None):
        """Send a message to a Kafka topic"""
        if not self.producer:
            logger.error("Kafka producer not initialized")
            # Try to reinitialize the producer
            self._init_producer()
            if not self.producer:
                return False
        
        try:
            # Send the message
            future = self.producer.send(topic, key=key, value=value)
            # Wait for the message to be delivered with a shorter timeout
            record_metadata = future.get(timeout=5)
            logger.info(f"Message sent to topic {record_metadata.topic} partition {record_metadata.partition} offset {record_metadata.offset}")
            return True
        except Exception as e:
            logger.error(f"Failed to send message to Kafka: {e}")
            # If we get a connection error, try to reinitialize the producer
            if "NoBrokersAvailable" in str(e) or "ConnectionError" in str(e):
                logger.info("Attempting to reconnect to Kafka...")
                self._init_producer()
            return False
    
    def create_consumer(self, topic, group_id=None, auto_offset_reset='earliest'):
        """Create a Kafka consumer for a topic"""
        try:
            consumer = KafkaConsumer(
                topic,
                bootstrap_servers=self.bootstrap_servers,
                group_id=group_id,
                auto_offset_reset=auto_offset_reset,
                value_deserializer=lambda v: json.loads(v.decode('utf-8')),
                key_deserializer=lambda k: k.decode('utf-8') if k else None,
                request_timeout_ms=5000,  # 5 seconds timeout
                session_timeout_ms=10000,  # 10 seconds session timeout
                heartbeat_interval_ms=3000,  # 3 seconds heartbeat
                connections_max_idle_ms=10000,  # 10 seconds idle timeout
                reconnect_backoff_ms=1000,  # 1 second backoff
                reconnect_backoff_max_ms=5000  # 5 seconds max backoff
            )
            logger.info(f"Kafka consumer created for topic {topic}")
            return consumer
        except Exception as e:
            logger.error(f"Failed to create Kafka consumer: {e}")
            return None
    
    def start_consumer_thread(self, topic, message_handler, group_id=None):
        """Start a consumer in a background thread"""
        def consumer_thread():
            consumer = self.create_consumer(topic, group_id)
            if not consumer:
                return
            
            logger.info(f"Starting consumer thread for topic {topic}")
            try:
                for message in consumer:
                    try:
                        message_handler(message.key, message.value)
                    except Exception as e:
                        logger.error(f"Error processing message: {e}")
            except Exception as e:
                logger.error(f"Consumer thread error: {e}")
            finally:
                consumer.close()
        
        thread = threading.Thread(target=consumer_thread, daemon=True)
        thread.start()
        return thread
