import hashlib
import os
import secrets
from typing import Dict, Tuple, Optional
from repository import Repository


# Handles authentication state management with strict cryptographic principles.
class UserRepository(Repository):
    def __init__(self, data_dir: str):
        super().__init__(data_dir, "users.json")

    def _hash_password(self, password: str, salt: bytes = None) -> Tuple[str, str]:
        # Utilizes PBKDF2 (Password-Based Key Derivation Function 2) to mitigate
        # dictionary and rainbow table attacks. By enforcing 100,000 iterations,
        # brute-forcing derived hashes becomes computationally unfeasible.
        if salt is None:
            salt = os.urandom(16)
        key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100000)
        return salt.hex(), key.hex()

    def create_user(self, username: str, password: str) -> bool:
        if self.get_user(username) is not None:
            return False

        salt_hex, hash_hex = self._hash_password(password)
        self.data.append({"username": username, "salt": salt_hex, "hash": hash_hex})
        self.save_changes()
        return True

    def get_user(self, username: str) -> Optional[Dict]:
        return next((u for u in self.data if u.get("username") == username), None)

    def authenticate(self, username: str, password: str) -> bool:
        user = self.get_user(username)
        if not user:
            return False

        salt_bytes = bytes.fromhex(user["salt"])
        _, check_hash = self._hash_password(password, salt=salt_bytes)

        # Uses constant-time comparison (secrets.compare_digest) rather than the standard '==' operator.
        # This prevents Timing Attacks, where an attacker measures the exact microsecond a comparison fails
        # to incrementally guess a valid hash structure.
        return secrets.compare_digest(user["hash"], check_hash)
