"""Diagnostic log that only prints when it changes.

The loop runs every TICK_SECONDS, so a direct `print` in a failure path would print ~7 times per second.
`report(key, message)` only prints when `message` changes from the last call with the same `key`.
`detail` goes along in the print, but is not part of the comparison (position, hashes, values that change every tick).
`message=None` clears the state without printing: the next failure shows up again.
"""
import time

from config import DEBUG_LOG

last_messages = {}


def report(key, message, detail=""):
    if not DEBUG_LOG or last_messages.get(key) == message:
        return

    last_messages[key] = message
    if message is not None:
        print(f"[{time.strftime('%H:%M:%S')}] {key}: {message}{f' ({detail})' if detail else ''}")
