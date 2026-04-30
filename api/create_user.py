import os
import sys

from dotenv import load_dotenv
from user_repository import UserRepository

load_dotenv()
DATA_DIR = os.getenv("DATA_DIR", "data")


# CLI bootstrapping tool.
# Provides an administrative way to populate the user database outside of the web API flow,
# ensuring secure password hashing processes are utilized correctly from the start.
def main():
    if len(sys.argv) != 3:
        print("Verwendung: python create_user.py <username> <passwort>")
        sys.exit(1)

    username = sys.argv[1]
    password = sys.argv[2]

    repo = UserRepository(DATA_DIR)
    success = repo.create_user(username, password)

    if success:
        print(f"✅ User '{username}' wurde erfolgreich in {DATA_DIR} angelegt.")
    else:
        print(f"❌ Fehler: User '{username}' existiert bereits.")


if __name__ == "__main__":
    main()
