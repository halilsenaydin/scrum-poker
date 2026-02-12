import json
from contextlib import asynccontextmanager
from django.core.cache import cache, caches
from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .services import RoomService
from .constants import PokerConstant


def action(name):
    """
    Decorator to register action handlers.

    Args:
        name: Action name.
    """

    def decorator(func):
        func._action_name = name

        return func

    return decorator


class RoomConsumer(AsyncWebsocketConsumer):
    """
    Room WebSocket consumer for handling poker room interactions.

    Args:
        AsyncWebsocketConsumer : Base class for WebSocket consumers.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.action_handlers = {}

        for attr_name in dir(self):
            attr = getattr(self, attr_name)

            if callable(attr) and hasattr(attr, "_action_name"):
                self.action_handlers[attr._action_name] = attr

    async def receive(self, text_data):
        """
        Handle incoming WebSocket messages.

        Args:
            text_data: Received WebSocket message.
        """
        data = json.loads(text_data)
        action = data.get("action")
        handler = self.action_handlers.get(action)

        if handler:
            await handler(data)

    async def connect(self):
        """
        Handle new WebSocket connection.
        """
        self.room_id = self.scope["url_route"]["kwargs"]["room_id"]
        self.room_group_name = f"room_{self.room_id}"

        # Add user to the room group
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

        # Load initial room state
        state = await self.get_room_state()
        participants = [
            {"name": name, "vote": data["vote"]}
            for name, data in state["participants"].items()
        ]

        await self.participants_update(
            {
                "participants": participants,
                "revealed": state["revealed"],
            }
        )

    async def disconnect(self, _):
        """
        Handle WebSocket disconnection.
        """
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    def room_cache_key(self):
        """
        Returns the cache key for the room.

        Returns:
            str: Cache key for the room.
        """
        return f"room:{self.room_id}"

    def room_lock_key(self):
        """
        Returns the cache key for the room lock.

        Returns:
            str: Cache key for the room lock.
        """
        return f"lock:room:{self.room_id}"

    async def get_room_state(self):
        """
        Retrieves the current state of the room from database.

        Returns:
            dict: Current state of the room.
        """
        state = await self.get_room_data()

        return state

    async def save_state(self, state, to_db=False):
        """
        Saves the current state of the room to cache and optionally to the database.

        Args:
            state (dict): Current state of the room.
            to_db (bool): Whether to save the state to the database.
        """
        cache.set(self.room_cache_key(), state, timeout=None)

        if to_db:
            await self.save_state_to_db(state)

    @database_sync_to_async
    def save_state_to_db(self, state):
        """
        Saves the current state of the room to the database.

        Args:
            state (dict): Current state of the room.
        """
        RoomService().update_room(self.room_id, state)

    @database_sync_to_async
    def get_room_data(self):
        """
        Gets the room data from the database.

        Returns:
            dict: Room data from the database.
        """
        return RoomService().get_room(self.room_id) or {
            "participants": {},
            "revealed": False,
        }

    @asynccontextmanager
    async def room_lock(self, timeout=5):
        """
        Returns an async context manager for acquiring a lock on the room.

        Args:
            timeout (int): Lock timeout in seconds.

        Raises:
            TimeoutError: If the lock cannot be acquired within the timeout.

        Returns:
            Async context manager for the room lock.
        """
        cache = caches["default"]
        client = cache.client.get_client()

        @sync_to_async
        def acquire_lock():
            """
            Acquires the lock for the room.

            Returns:
                lock object if acquired, None otherwise.
            """
            lock = client.lock(self.room_lock_key(), timeout=timeout)
            acquired = lock.acquire(blocking=True)

            return lock if acquired else None

        lock = await acquire_lock()

        if not lock:
            raise TimeoutError(f"Lock alınamadı: {self.room_name}")

        try:
            yield
        finally:

            @sync_to_async
            def release_lock():
                """
                Releases the lock for the room.
                """
                if lock.owned():
                    lock.release()

            await release_lock()

    @action("join")
    async def handle_join(self, data):
        """
        Handle participant joining the room.

        Args:
            data (dict): Data containing participant information.
        """
        name = (data.get("name") or "Anonymous").strip() or "Anonymous"

        async with self.room_lock():
            state = await self.get_room_state()
            state["participants"].setdefault(name, {"vote": None})

            await self.save_state(state, to_db=True)
            await self.send_participants_update(state)

    @action("vote")
    async def handle_vote(self, data):
        """
        Handle participant voting.

        Args:
            data (dict): Data containing participant vote information.
        """
        name, value = data.get("name"), data.get("value")

        if value not in PokerConstant.POINTS:
            return

        async with self.room_lock():
            state = await self.get_room_state()
            state["participants"].setdefault(name, {"vote": None})
            state["participants"][name]["vote"] = value
            state["revealed"] = False

            await self.save_state(state, to_db=True)
            await self.send_participants_update(state)

    @action("remove_participant")
    async def handle_remove_participant(self, data):
        """
        Handle participant removal.

        Args:
            data (dict): Data containing participant information.
        """
        name = data.get("name")

        async with self.room_lock():
            state = await self.get_room_state()
            state["participants"].pop(name, None)

            await self.save_state(state, to_db=True)
            await self.send_participants_update(state)

    @action("reveal")
    async def handle_reveal(self, _):
        """
        Handle revealing votes.
        """
        async with self.room_lock():
            state = await self.get_room_state()
            state["revealed"] = True

            await self.save_state(state, to_db=True)
            await self.send_participants_update(state)

    @action("reset")
    async def handle_reset(self, _):
        """
        Handle resetting votes.
        """
        async with self.room_lock():
            state = await self.get_room_state()

            for p in state["participants"].values():
                p["vote"] = None

            state["revealed"] = False

            await self.save_state(state, to_db=True)
            await self.send_participants_update(state)

    async def send_participants_update(self, state):
        """
        Sends the updated participants list to all clients.

        Args:
            state (dict): Current state of the room.
        """
        current_participants = state["participants"]
        revealed = state["revealed"]
        payload_participants = [
            {"name": name, "vote": data["vote"]}
            for name, data in current_participants.items()
        ]

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "participants_update",
                "participants": payload_participants,
                "revealed": revealed,
            },
        )

    async def participants_update(self, event):
        """
        Processes participants update events.

        Args:
            event (dict): Event data containing participants update.
        """
        await self.send(text_data=json.dumps(event))
