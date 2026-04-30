# Custom exception hierarchy. Creating specific exceptions rather than using
# built-in Exception classes allows higher layers to catch and handle
# domain-specific errors predictably.
class ChatException(Exception):
    pass
