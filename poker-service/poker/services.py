from __future__ import annotations
import secrets
import string
from typing import Optional
from firebase_admin import credentials, firestore, initialize_app
from django.conf import settings
from django.utils.translation import gettext as _
from django.contrib.auth.hashers import check_password, make_password


class FirestoreClient:
    """
    Firebase Firestore client singleton

    Returns:
        firestore.Client: Firestore client instance
    """

    _client = None

    @classmethod
    def get_client(cls):
        if cls._client is None:
            cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS)

            initialize_app(cred)

            cls._client = firestore.client(database_id="scrum-poker")

        return cls._client


class BusinessRule:
    """
    Business rule for validation
    """

    def __init__(self, error_condition: bool, error_message: str):
        self.error_condition = error_condition
        self.error_message = error_message

    @staticmethod
    def run(rules: list[BusinessRule]) -> str | None:
        """
        Evaluate business rules and return the first error message if any rule fails

        Args:
            rules (list[BusinessRule]): List of business rules to evaluate

        Returns:
            str | None: Error message of the first failed rule or None if all pass
        """
        for rule in rules:
            if rule.error_condition:
                return rule.error_message

        return None


class Result:
    """
    Standard result object for service methods
    """

    def __init__(self, status: bool, message: str, data=None):
        self.status = status
        self.message = message
        self.data = data


class ResultUtil:
    """
    Result utility class for creating standard result objects

    Returns:
        Result: Standard result object
    """

    @staticmethod
    def result(status: bool, message: str, data=None) -> Result:
        """
        Create a standard result object

        Args:
            status (bool): Whether the operation was successful.
            message (str): A message describing the result.
            data (_type_, optional): Additional data to include in the result. Defaults to None.

        Returns:
            Result: A standard result object.
        """
        return Result(status, message, data)

    @staticmethod
    def success_result(message: str, data=None) -> Result:
        """
        Success result factory method

        Args:
            message (str): A message describing the result.
            data (_type_, optional): Additional data to include in the result. Defaults to None.

        Returns:
            Result: A standard result object.
        """
        return ResultUtil.result(True, message, data)

    @staticmethod
    def error_result(message: str, data=None) -> Result:
        """
        Error result factory method

        Args:
            message (str): A message describing the error.
            data (_type_, optional): Additional data to include in the result. Defaults to None.

        Returns:
            Result: A standard result object.
        """
        return ResultUtil.result(False, message, data)


class RoomService:
    """
    Room service for managing poker rooms
    """

    def __init__(self):
        self.db = FirestoreClient.get_client()
        self.rooms = self.db.collection("rooms")

    def generate_token(self, room_code: str, room_password: str) -> str:
        return f"{room_code}:{room_password}"

    def create_room(self, password: str, room_code: Optional[str] = None, hash: bool = True) -> Result:
        """
        Create a new poker room with the given password

        Args:
            password (str): The password for the room

        Returns:
            Result: Result object indicating success or failure
        """
        if not room_code:
            room_code = self._generate_unique_room_code()

        rules = [BusinessRule(not password, _("message_room_password_required"))]
        error = BusinessRule.run(rules)

        if error:
            return ResultUtil.error_result(error)

        if hash:
            password = make_password(password)

        data = self.create_room_record(room_code, password)

        return ResultUtil.success_result(_("message_room_created_success") % {"room_id": room_code}, data)

    def create_room_record(self, room_code: str, password: str):
        """
        Create a room record in Firestore

        Args:
            room_code (str): The unique code for the room
            password (str): The password for the room

        Returns:
            dict: The created room record
        """
        data = {
            "room_code": room_code,
            "password": password,
            "is_open": True,
            "participants": {},
            "revealed": False,
        }

        self.rooms.document(room_code).set(data)

        return data

    def join_room(self, room_code: str, password: str):
        """
        Join a poker room with the given room code and password

        Args:
            room_code (str): The code of the room to join
            password (str): The password for the room

        Returns:
            Result: A standard result object.
        """
        room = self.get_room(room_code)
        rules = [
            BusinessRule(not room_code or not password, _("message_fill_all_fields")),
            BusinessRule(not room, _("message_room_not_found")),
            BusinessRule(
                room and not check_password(password, room.get("password")), _("message_wrong_password")
            ),
            BusinessRule(
                room and not room.get("is_open", True), _("message_room_closed")
            ),
        ]
        error = BusinessRule.run(rules)

        if error:
            return ResultUtil.error_result(error)

        return ResultUtil.success_result(None, room)

    def get_room(self, room_code: str):
        """
        Get a poker room by its code

        Args:
            room_code (str): The code of the room to retrieve

        Returns:
            dict: The retrieved room record or None if not found.
        """
        doc = self.rooms.document(room_code).get()

        return doc.to_dict() if doc.exists else None

    def update_room(self, room_code: str, payload: dict):
        """
        Update a poker room with the given payload

        Args:
            room_code (str): The code of the room to update
            payload (dict): The data to update the room with
        """
        self.rooms.document(room_code).update(payload)

    def add_participant(self, room_id, name):
        """
        Add a participant to the room

        Args:
            room_id (str): The ID of the room to add the participant to
            name (str): The name of the participant to add
        """
        room = self.get_room(room_id)
        participants = room.get("participants", {})

        if name not in participants:
            participants[name] = {"vote": None}
            room["participants"] = participants

            self.update_room(room_id, room)

    def remove_participant(self, room_id, name):
        """
        Remove a participant from the room

        Args:
            room_id (str): The ID of the room to remove the participant from
            name (str): The name of the participant to remove
        """
        room = self.get_room(room_id)
        participants = room.get("participants", {})

        if name in participants:
            participants.pop(name)

            room["participants"] = participants

            self.update_room(room_id, room)

    def update_vote(self, room_id, name, value):
        """
        Update a participant's vote in the room

        Args:
            room_id (str): The ID of the room to update the vote in
            name (str): The name of the participant to update
            value (int): The new vote value for the participant
        """
        room = self.get_room(room_id)
        participants = room.get("participants", {})

        if name in participants:
            participants[name]["vote"] = value
            room["participants"] = participants

            self.update_room(room_id, room)

    def reset_votes(self, room_id):
        """
        Reset all participants' votes in the room

        Args:
            room_id (str): The ID of the room to reset votes in
        """
        room = self.get_room(room_id)
        participants = room.get("participants", {})

        for name in participants:
            participants[name]["vote"] = None

        room["participants"] = participants

        self.update_room(room_id, room)

    def _generate_unique_room_code(self):
        """
        Generate a unique room code

        Returns:
            str: A unique room code.
        """
        while True:
            code = self._generate_room_code()

            if not self.get_room(code):
                return code

    def _generate_room_code(self):
        """
        Generate a random room code

        Returns:
            str: A random room code.
        """
        return "".join(
            secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6)
        )
