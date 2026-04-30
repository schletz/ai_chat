import os
import sys

from dotenv import load_dotenv
from user_repository import UserRepository

load_dotenv()
DATA_DIR = os.getenv("DATA_DIR", "data")


def main():
    """Execute the CLI command to create a new user.

    Parses command-line arguments for username and password,
    instantiates the repository, and attempts user creation.
    Exits with status code 1 if arguments are missing or an error occurs.
    """
    if len(sys.argv) != 3:
        print("Usage: python create_user.py <username> <password>")
        sys.exit(1)

    username = sys.argv[1]
    password = sys.argv[2]

    repo = UserRepository(DATA_DIR)
    success = repo.create_user(username, password)

    if success:
        print(f"✅ User '{username}' was successfully created in {DATA_DIR}.")
    else:
        print(f"❌ Error: User '{username}' already exists.")


if __name__ == "__main__":
    main()