#!/usr/bin/env python3
"""
Example script demonstrating how to track Notion block changes using Kafka.
This script initializes a Notion client with Kafka enabled and monitors changes.
"""
import os
import sys
import time
import logging
import argparse
from dotenv import load_dotenv

# Add the parent directory to the path so we can import the notion package
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from notion.client import NotionClient
from notion.block import PageBlock, TextBlock

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Track Notion Changes with Kafka')
    parser.add_argument('--token', type=str, help='Notion token_v2 cookie value')
    parser.add_argument('--page-url', type=str, help='URL of a Notion page to modify')
    parser.add_argument('--bootstrap-servers', type=str, default='localhost:9092', 
                        help='Kafka bootstrap servers')
    
    args = parser.parse_args()
    
    # Load environment variables from .env file
    load_dotenv()
    
    # Get token from environment if not provided
    token = args.token or os.environ.get('NOTION_TOKEN')
    if not token:
        logger.error("Notion token not provided. Use --token or set NOTION_TOKEN environment variable.")
        return
    
    # Get page URL from environment if not provided
    page_url = args.page_url or os.environ.get('NOTION_PAGE_URL')
    if not page_url:
        logger.error("Notion page URL not provided. Use --page-url or set NOTION_PAGE_URL environment variable.")
        return
    
    # Initialize Notion client with Kafka enabled
    logger.info("Initializing Notion client with Kafka enabled")
    client = NotionClient(
        token_v2=token,
        monitor=True,  # Enable monitoring for real-time updates
        start_monitoring=True,  # Start monitoring immediately
        enable_kafka=True,  # Enable Kafka integration
        kafka_bootstrap_servers=args.bootstrap_servers
    )
    
    # Get the page
    logger.info(f"Loading page: {page_url}")
    page = client.get_block(page_url)
    
    # Print page info
    logger.info(f"Page title: {page.title}")
    
    # Make some changes to the page to demonstrate event publishing
    logger.info("Making changes to the page...")
    
    # Add a new text block
    new_block = page.children.add_new(TextBlock, title=f"This is a test block added at {time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Added new block with ID: {new_block.id}")
    
    # Wait a moment
    time.sleep(2)
    
    # Update the block
    logger.info("Updating the block...")
    new_block.title = f"This block was updated at {time.strftime('%Y-%m-%d %H:%M:%S')}"
    
    # Wait a moment
    time.sleep(2)
    
    # Remove the block
    logger.info("Removing the block...")
    new_block.remove()
    
    logger.info("Done! Check your Kafka topic 'notion-events' for the published events.")
    logger.info("You can use the kafka_consumer.py script to view the events:")
    logger.info("python kafka_consumer.py --topic notion-events")
    
    # Keep the script running to continue monitoring events
    logger.info("Press Ctrl+C to exit...")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Exiting...")

if __name__ == "__main__":
    main()
