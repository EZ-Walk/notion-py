#!/usr/bin/env python3
"""
Standalone Kafka producer script to send test messages to Kafka topics
"""
import logging
import argparse
import json
import datetime
import os
from kafka_utils import KafkaClient

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_sample_message(topic, message_type=None):
    """Create a sample message based on the topic"""
    timestamp = str(datetime.datetime.now())
    
    if topic == 'user-activity':
        return {
            'event_type': message_type or 'login',
            'username': 'test_user',
            'timestamp': timestamp
        }
    elif topic == 'notion-events':
        return {
            'event_type': message_type or 'page_activated',
            'username': 'test_user',
            'page_id': '123456789abcdef',
            'page_title': 'Test Page',
            'timestamp': timestamp
        }
    else:
        return {
            'event_type': message_type or 'custom',
            'message': 'Test message',
            'timestamp': timestamp
        }

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Kafka Producer CLI')
    parser.add_argument('--topic', type=str, required=True, help='Kafka topic to produce to')
    parser.add_argument('--message-type', type=str, help='Type of message to send (event_type)')
    parser.add_argument('--key', type=str, help='Message key')
    parser.add_argument('--custom-message', type=str, help='Custom JSON message to send')
    # Check if we're running inside a container by looking for the KAFKA_BOOTSTRAP_SERVERS env var
    default_bootstrap = os.environ.get('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')
    parser.add_argument('--bootstrap-servers', type=str, default=default_bootstrap, 
                        help='Kafka bootstrap servers')
    
    args = parser.parse_args()
    
    logger.info(f"Starting Kafka producer for topic: {args.topic}")
    logger.info(f"Using bootstrap servers: {args.bootstrap_servers}")
    
    # Initialize Kafka client
    kafka_client = KafkaClient(bootstrap_servers=args.bootstrap_servers)
    
    # Create message
    if args.custom_message:
        try:
            message = json.loads(args.custom_message)
        except json.JSONDecodeError:
            logger.error("Invalid JSON in custom message")
            return
    else:
        message = create_sample_message(args.topic, args.message_type)
    
    # Send message
    success = kafka_client.send_message(args.topic, message, args.key)
    
    if success:
        logger.info(f"Successfully sent message to topic {args.topic}")
        logger.info(f"Message: {message}")
    else:
        logger.error(f"Failed to send message to topic {args.topic}")

if __name__ == "__main__":
    main()