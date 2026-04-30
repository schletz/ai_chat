import base64
import json
import os
from typing import Any, List


class Repository:
    """Base repository handling physical file input and output operations."""

    def __init__(self, data_dir: str, datafile: str):
        """Initialize the repository with directory and filename paths.

        Creates the target directory if it does not exist. Initializes internal state
        by loading existing data or creating a new empty dataset.
        """
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)
        self.data_dir = data_dir
        self.datafile = os.path.join(data_dir, datafile)
        self.data = []
        if not os.path.exists(self.datafile) or os.path.getsize(self.datafile) == 0:
            self.save_changes()
        else:
            self.data = self.read_data()

    def read_data(self) -> List:
        """Read and parse JSON data from the repository file."""
        with open(self.datafile, "r", encoding="utf-8") as f:
            return json.load(f)

    def save_changes(self) -> None:
        """Serialize internal state to JSON and write it to the repository file."""
        with open(self.datafile, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=4, ensure_ascii=False)

    def encode_filename_part(self, name: str) -> str:
        """Encode a string component into a URL-safe base64 format for filenames.

        Neutralizes path traversal characters by converting the input to base64.
        Returns an empty string if the input is falsy.
        """
        if not name:
            return ""
        encoded_bytes = base64.urlsafe_b64encode(name.encode("utf-8"))
        return encoded_bytes.decode("utf-8").rstrip("=")