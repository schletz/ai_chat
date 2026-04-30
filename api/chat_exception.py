class ChatException(Exception):
    """Custom exception for domain-specific chat errors.

    This allows calling layers to catch and handle them specifically via try-except blocks,
    rather than relying on generic exceptions.
    """
