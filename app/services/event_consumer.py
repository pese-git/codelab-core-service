"""Event consumer for Redis Streams"""

import asyncio
import json
import logging
from typing import Callable, Optional
from datetime import datetime, timezone

from redis import Redis
from redis.exceptions import ConnectionError as RedisConnectionError

logger = logging.getLogger(__name__)


class EventConsumer:
    """
    Consumer for receiving and processing events from Redis Streams.
    
    Implements Consumer Groups for reliable message delivery with retry logic,
    pending message handling, and dead letter queue support.
    """

    STREAM_KEY = "user_events"
    CONSUMER_GROUP = "core_service_group"
    CONSUMER_NAME = "core_service_1"
    DLQ_STREAM_KEY = "user_events_dlq"
    
    # Configuration
    BLOCK_MS = 100  # Blocking read timeout
    BATCH_SIZE = 10  # Messages per batch
    MIN_IDLE_MS = 60000  # 60 seconds for XAUTOCLAIM
    MAX_RETRIES = 5  # Max retry attempts
    INITIAL_BACKOFF = 1  # seconds
    MAX_BACKOFF = 60  # seconds

    def __init__(self, redis: Redis):
        """
        Initialize the event consumer.
        
        Args:
            redis: Redis client (redis.asyncio.Redis or redis.Redis)
        """
        self.redis = redis
        self.handlers: dict[str, Callable] = {}
        self.running = False
        self.task: Optional[asyncio.Task] = None

    async def initialize(self) -> None:
        """
        Initialize consumer group and DLQ stream.
        
        Creates consumer group if not exists, otherwise uses existing one.
        Creates DLQ stream for failed messages.
        
        Raises:
            RedisConnectionError: if Redis is unavailable
        """
        try:
            # Test connection
            await self.redis.ping()
            logger.info("Redis connection successful")
            
            # Create consumer group
            try:
                await self.redis.xgroup_create(
                    self.STREAM_KEY,
                    self.CONSUMER_GROUP,
                    id="$",  # Start reading from new messages
                    mkstream=True,  # Create stream if not exists
                )
                logger.info(
                    f"Consumer group created: {self.CONSUMER_GROUP}"
                )
            except Exception as e:
                if "BUSYGROUP" in str(e):
                    logger.info(
                        f"Consumer group already exists: {self.CONSUMER_GROUP}"
                    )
                else:
                    raise
            
            # Create DLQ stream (just verify existence)
            stream_info = await self.redis.xlen(self.DLQ_STREAM_KEY)
            logger.info(f"DLQ stream initialized: {self.DLQ_STREAM_KEY}")
            
            logger.info("Event consumer initialized successfully")

        except RedisConnectionError as e:
            logger.error(f"Redis connection error during initialization: {e}")
            raise

    def register_handler(
        self,
        event_type: str,
        handler: Callable,
    ) -> None:
        """
        Register event handler for specific event type.
        
        Args:
            event_type: Event type (e.g., "user.created", "user.deleted")
            handler: Async callable that accepts event dict
        
        Example:
            >>> consumer = EventConsumer(redis)
            >>> consumer.register_handler("user.deleted", handle_user_deleted)
        """
        self.handlers[event_type] = handler
        logger.info(f"Handler registered for event type: {event_type}")

    async def start(self) -> None:
        """
        Start the consumer loop (blocking operation).
        
        Processes messages in loop:
        1. XAUTOCLAIM pending messages (stalled consumers)
        2. XREADGROUP new messages
        3. Call handler for each message
        4. XACK on success, send to DLQ on failure
        
        Raises:
            asyncio.CancelledError: when stop() is called
        """
        self.running = True
        logger.info("Event consumer started")
        
        try:
            while self.running:
                try:
                    # Phase 1: Handle pending messages (XAUTOCLAIM)
                    await self._process_pending_messages()
                    
                    # Phase 2: Read new messages (XREADGROUP)
                    await self._process_new_messages()
                    
                except asyncio.CancelledError:
                    logger.info("Consumer loop cancelled (shutdown)")
                    break
                except RedisConnectionError as e:
                    logger.error(f"Redis connection error: {e}")
                    await asyncio.sleep(5)  # Wait before retry
                except Exception as e:
                    logger.error(f"Unexpected error in consumer loop: {e}")
                    await asyncio.sleep(1)

        finally:
            self.running = False
            logger.info("Event consumer stopped")

    async def stop(self) -> None:
        """
        Stop the consumer loop gracefully.
        
        Allows pending messages to be processed before stopping.
        """
        logger.info("Stopping event consumer...")
        self.running = False
        
        if self.task and not self.task.done():
            await self.task

    async def _process_pending_messages(self) -> None:
        """
        Process messages that are pending (stalled from previous consumer).
        
        Uses XAUTOCLAIM to take ownership of messages that haven't been
        ACKed within MIN_IDLE_MS.
        """
        try:
            # XAUTOCLAIM returns messages idle for more than 60 seconds
            pending_messages = await self.redis.xautoclaim(
                self.STREAM_KEY,
                self.CONSUMER_GROUP,
                self.CONSUMER_NAME,
                self.MIN_IDLE_MS,
                "0-0",  # Start from beginning
                count=self.BATCH_SIZE,
            )
            
            if pending_messages:
                logger.debug(
                    f"Processing {len(pending_messages)} pending messages"
                )
                
                for message_id, message_data in pending_messages:
                    await self._process_message(message_id, message_data)

        except Exception as e:
            logger.error(f"Error processing pending messages: {e}")

    async def _process_new_messages(self) -> None:
        """
        Process new messages from the stream.
        
        Uses XREADGROUP to read messages assigned to this consumer.
        """
        try:
            messages = await self.redis.xreadgroup(
                {self.STREAM_KEY: ">"},  # > = new messages not yet delivered
                self.CONSUMER_GROUP,
                self.CONSUMER_NAME,
                count=self.BATCH_SIZE,
                block=self.BLOCK_MS,
            )
            
            if messages:
                # messages is list of (stream_key, [(message_id, data), ...])
                for stream_key, message_list in messages:
                    for message_id, message_data in message_list:
                        await self._process_message(message_id, message_data)

        except Exception as e:
            logger.error(f"Error reading new messages: {e}")

    async def _process_message(
        self,
        message_id: bytes | str,
        message_data: dict,
    ) -> None:
        """
        Process a single message from the stream.
        
        Args:
            message_id: Redis Stream message ID
            message_data: Message data dict
        """
        try:
            # Convert message ID to string if needed
            if isinstance(message_id, bytes):
                message_id = message_id.decode()
            
            # Parse message data
            event = await self._parse_event(message_data)
            
            if not event:
                logger.warning(f"Failed to parse event: {message_data}")
                await self._send_to_dlq(message_id, message_data, "parse_error")
                await self.redis.xack(
                    self.STREAM_KEY,
                    self.CONSUMER_GROUP,
                    message_id,
                )
                return
            
            # Get event type
            event_type = event.get("event_type")
            
            if not event_type:
                logger.warning(f"Event missing type: {event}")
                await self._send_to_dlq(message_id, message_data, "missing_type")
                await self.redis.xack(
                    self.STREAM_KEY,
                    self.CONSUMER_GROUP,
                    message_id,
                )
                return
            
            # Get handler for event type
            handler = self.handlers.get(event_type)
            
            if not handler:
                logger.warning(f"No handler for event type: {event_type}")
                await self._send_to_dlq(
                    message_id,
                    message_data,
                    f"no_handler_for_{event_type}"
                )
                await self.redis.xack(
                    self.STREAM_KEY,
                    self.CONSUMER_GROUP,
                    message_id,
                )
                return
            
            # Call handler with retry logic
            retry_count = 0
            while retry_count < self.MAX_RETRIES:
                try:
                    logger.debug(
                        f"Processing event: id={event.get('event_id')}, "
                        f"type={event_type}"
                    )
                    
                    await handler(event)
                    
                    # Success: ACK the message
                    await self.redis.xack(
                        self.STREAM_KEY,
                        self.CONSUMER_GROUP,
                        message_id,
                    )
                    
                    logger.info(
                        f"Event processed successfully: "
                        f"id={event.get('event_id')}, type={event_type}"
                    )
                    
                    return

                except Exception as e:
                    retry_count += 1
                    
                    if retry_count >= self.MAX_RETRIES:
                        logger.error(
                            f"Handler failed after {self.MAX_RETRIES} retries: "
                            f"event_type={event_type}, error={str(e)}"
                        )
                        await self._send_to_dlq(
                            message_id,
                            message_data,
                            f"handler_failed_{event_type}"
                        )
                        await self.redis.xack(
                            self.STREAM_KEY,
                            self.CONSUMER_GROUP,
                            message_id,
                        )
                        return
                    
                    # Calculate backoff
                    backoff = min(
                        self.INITIAL_BACKOFF * (2 ** (retry_count - 1)),
                        self.MAX_BACKOFF
                    )
                    
                    logger.warning(
                        f"Handler failed (retry {retry_count}/{self.MAX_RETRIES}): "
                        f"event_type={event_type}, error={str(e)}, "
                        f"backoff={backoff}s"
                    )
                    
                    await asyncio.sleep(backoff)

        except Exception as e:
            logger.error(f"Unexpected error processing message: {e}")

    async def _parse_event(
        self,
        message_data: dict,
    ) -> Optional[dict]:
        """
        Parse event from Redis message data.
        
        Converts bytes to strings and deserializes JSON payloads.
        
        Args:
            message_data: Raw message data from Redis
        
        Returns:
            Parsed event dict or None if parsing fails
        """
        try:
            # Convert bytes to strings
            event = {}
            
            for key, value in message_data.items():
                # Decode key
                if isinstance(key, bytes):
                    key = key.decode()
                
                # Decode value
                if isinstance(value, bytes):
                    value = value.decode()
                
                # Parse JSON fields
                if key == "data":
                    try:
                        value = json.loads(value)
                    except (json.JSONDecodeError, TypeError):
                        logger.warning(f"Failed to parse data field: {value}")
                        pass
                
                event[key] = value
            
            return event

        except Exception as e:
            logger.error(f"Error parsing event: {e}")
            return None

    async def _send_to_dlq(
        self,
        message_id: str,
        message_data: dict,
        reason: str,
    ) -> None:
        """
        Send message to dead letter queue (DLQ).
        
        Args:
            message_id: Original message ID
            message_data: Original message data
            reason: Reason for DLQ (e.g., "handler_failed")
        """
        try:
            dlq_message = {
                "original_message_id": message_id,
                "original_data": json.dumps(message_data, default=str),
                "dlq_reason": reason,
                "dlq_timestamp": datetime.now(timezone.utc).isoformat(),
            }
            
            await self.redis.xadd(
                self.DLQ_STREAM_KEY,
                dlq_message,
            )
            
            logger.info(
                f"Message sent to DLQ: id={message_id}, reason={reason}"
            )

        except Exception as e:
            logger.error(f"Failed to send message to DLQ: {e}")


# Global service instance
_event_consumer: Optional[EventConsumer] = None


async def init_event_consumer(redis: Redis) -> EventConsumer:
    """
    Initialize the event consumer with Redis client.
    
    Args:
        redis: Redis client instance
    
    Returns:
        EventConsumer instance
    """
    global _event_consumer
    _event_consumer = EventConsumer(redis)
    await _event_consumer.initialize()
    logger.info("Event consumer initialized")
    return _event_consumer


async def get_event_consumer() -> EventConsumer:
    """
    Get the event consumer instance.
    
    Returns:
        EventConsumer instance
    
    Raises:
        RuntimeError: if consumer not initialized
    """
    if _event_consumer is None:
        raise RuntimeError("Event consumer not initialized")
    return _event_consumer
