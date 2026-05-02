import os
import sys

from dotenv import load_dotenv
from user_repository import UserRepository

load_dotenv()
DATA_DIR = os.getenv("DATA_DIR", "data")


# CLI-Tool (Command Line Interface) für die Ersteinrichtung.
# Bietet eine administrative Möglichkeit, neue Nutzer außerhalb der Web-API anzulegen.
# So wird sichergestellt, dass die Passwörter von Anfang an korrekt gehasht werden.
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
