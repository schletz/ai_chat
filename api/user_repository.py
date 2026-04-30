import hashlib
import os
import secrets
from typing import List, Tuple, Optional, TypedDict
from repository import Repository

class UserEntry(TypedDict):
    """Typed dict for a user entry."""
    username: str
    salt: str
    hash: str

class UserRepository(Repository):
    """Manages user logins while adhering to cryptographic best practices."""

    def __init__(self, data_dir: str) -> None:
        super().__init__(data_dir, "users.json")

    def _hash_password(self, password: str, salt: Optional[bytes] = None) -> Tuple[str, str]:
        """Hash a password using PBKDF2 with a generated or provided salt.

        @param password: The plaintext password to hash.
        @param salt: Optional cryptographic salt. Generated if not provided.
        @returns: A tuple containing the hex-encoded salt and the hex-encoded derived key.
        """
        if salt is None:
            salt = os.urandom(16)
        key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100000)
        return salt.hex(), key.hex()

    def create_user(self, username: str, password: str) -> bool:
        """Create a new user account with a securely hashed password.

        @param username: The desired username.
        @param password: The plaintext password to hash and store.
        @returns: True if the user was created successfully, False otherwise.
        """
        if self.get_user(username) is not None:
            return False

        salt_hex, hash_hex = self._hash_password(password)
        self.data.append({"username": username, "salt": salt_hex, "hash": hash_hex})
        self.save_changes()
        return True

    def get_user(self, username: str) -> Optional[UserEntry]:
        """Retrieve a user record by username.

        @param username: The username to search for.
        @returns: The user dictionary if found, None otherwise.
        """
        return next((u for u in self.data if u.get("username") == username), None)

    def get_users(self) -> List[str]:
        """Retrieve a list of all registered usernames."""
        return [u.get("username") for u in self.data]

    def authenticate(self, username: str, password: str) -> bool:
        """Verify a user's credentials against stored hashes.

        @param username: The username to verify.
        @param password: The plaintext password to check.
        @returns: True if the credentials match, False otherwise.
        """
        user = self.get_user(username)
        if not user:
            return False

        salt_bytes = bytes.fromhex(user["salt"])
        _, check_hash = self._hash_password(password, salt=salt_bytes)

        # Perform constant-time comparison to prevent timing attacks.
        return secrets.compare_digest(user["hash"], check_hash)