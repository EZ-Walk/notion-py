#!/usr/bin/env python3
"""
Standalone Kafka consumer script to monitor topics
"""
import logging
import argparse
import os
from kafka_utils import KafkaClient

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def message_handler(key, value):
    """Handle incoming Kafka messages"""
    key_str = f"[{key}]" if key else ""
    logger.info(f"Received message {key_str}: {value}")

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Kafka Consumer CLI')
    parser.add_argument('--topic', type=str, required=True, help='Kafka topic to consume')
    parser.add_argument('--group', type=str, default=None, help='Consumer group ID')
    # Check if we're running inside a container by looking for the KAFKA_BOOTSTRAP_SERVERS env var
    default_bootstrap = os.environ.get('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')
    parser.add_argument('--bootstrap-servers', type=str, default=default_bootstrap, 
                        help='Kafka bootstrap servers')
    
    args = parser.parse_args()
    
    logger.info(f"Starting Kafka consumer for topic: {args.topic}")
    logger.info(f"Using bootstrap servers: {args.bootstrap_servers}")
    
    # Initialize Kafka client
    kafka_client = KafkaClient(bootstrap_servers=args.bootstrap_servers)
    
    # Create consumer
    consumer = kafka_client.create_consumer(args.topic, args.group)
    if not consumer:
        logger.error("Failed to create consumer. Exiting.")
        return
    
    try:
        logger.info(f"Consumer started. Listening for messages on topic: {args.topic}")
        for message in consumer:
            message_handler(message.key, message.value)
    except KeyboardInterrupt:
        logger.info("Consumer stopped by user")
    except Exception as e:
        logger.error(f"Error in consumer: {e}")
    finally:
        consumer.close()
        logger.info("Consumer closed")

if __name__ == "__main__":
    main()