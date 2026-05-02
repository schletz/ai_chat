import hashlib
import os
import secrets
from typing import Dict, Tuple, Optional
from repository import Repository


# Verwaltet die Benutzer-Logins unter strikter Einhaltung kryptographischer Best Practices.
class UserRepository(Repository):
    def __init__(self, data_dir: str):
        super().__init__(data_dir, "users.json")

    def _hash_password(self, password: str, salt: bytes = None) -> Tuple[str, str]:
        # Nutzung von PBKDF2 (Password-Based Key Derivation Function 2).
        # Algorithmen wie MD5 oder SHA256 sind zu schnell und daher anfällig für Brute-Force oder Rainbow-Tables.
        # PBKDF2 wendet den Hash-Algorithmus (hier 100.000 Mal) immer wieder an. Das macht das Hashen absichtlich
        # langsam und vereitelt dadurch massenhafte Ausprobier-Attacken (Brute Force).
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

        # Konstante-Zeit-Vergleich (`secrets.compare_digest`) anstelle des normalen `==` Operators.
        # Ein normales `==` bricht ab, sobald das erste Zeichen falsch ist. Ein Angreifer könnte durch
        # das Messen von Mikrosekunden-Verzögerungen (Timing Attack) Zeichen für Zeichen das richtige Passwort erraten.
        return secrets.compare_digest(user["hash"], check_hash)
