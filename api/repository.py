import base64
import json
import os
from typing import Any, List


# The foundational Base Repository. Encapsulates physical file I/O operations,
# ensuring that domain repositories inherit standardized data serialization processes.
class Repository:
    def __init__(self, data_dir: str, datafile: str):
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
        with open(self.datafile, "r", encoding="utf-8") as f:
            return json.load(f)

    def save_changes(self) -> None:
        with open(self.datafile, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=4, ensure_ascii=False)

    def encode_filename_part(self, name: str) -> str:
        # Crucial security mechanism: Encodes arbitrary string identifiers into URL-safe Base64.
        # This completely neutralizes Path Traversal (Directory Traversal) vulnerability vectors
        # by stripping special path characters like '/' and '\' from dynamically generated filenames.
        if not name:
            return ""
        encoded_bytes = base64.urlsafe_b64encode(name.encode("utf-8"))
        return encoded_bytes.decode("utf-8").rstrip("=")
