"""
WebSocket client that runs in a background thread.
Connects to WS_SERVER_URL, sends a greeting, and prints any messages received.

Movement messages of the form "DOOM: <key>" update ws_keys on the player so
that player.control() can treat them as held keys.  Recognised keys:
    W, A, S, D, leftarrow, rightarrow
"""
import asyncio
import collections
import threading
import time

import websockets

from doomsettings import WS_SERVER_URL

RECONNECT_DELAY = 5   # seconds between reconnect attempts
# A ws key is considered "held" for this many seconds after the last message.
# The mobile client should send repeated messages (~10/s) while a button is held.
WS_KEY_TIMEOUT = 0.15  # seconds

MOVEMENT_KEYS = {"W", "A", "S", "D", "leftarrow", "rightarrow"}
ACTION_KEYS    = {"fire", "interact", "talk mode on", "talk mode off"}


class WSClient:
    def __init__(self):
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._stop_event = asyncio.Event()
        # Filled by background thread, read by game loop.
        # Maps key name -> monotonic timestamp of last "press" message.
        self.ws_keys: dict[str, float] = {}
        # One-shot actions queued by background thread, drained each frame.
        self.pending_actions: collections.deque[str] = collections.deque()

    def start(self):
        self._thread.start()

    def stop(self):
        self._loop.call_soon_threadsafe(self._stop_event.set)

    def is_key_held(self, key: str) -> bool:
        """Return True if a WS movement key was pressed recently enough."""
        last = self.ws_keys.get(key, 0.0)
        return (time.monotonic() - last) < WS_KEY_TIMEOUT

    def _handle_message(self, message):
        if isinstance(message, bytes):
            message = message.decode("utf-8")
        print(f"[WS] {message}")
        if message.startswith("DOOM: "):
            key = message[6:].strip()
            if key in MOVEMENT_KEYS:
                self.ws_keys[key] = time.monotonic()
            elif key.startswith("speech "):
                self.pending_actions.append(key)   # full string e.g. "speech hello there"
            elif key in ACTION_KEYS:
                self.pending_actions.append(key)

    def _run_loop(self):
        self._loop.run_until_complete(self._connect_forever())
        self._loop.close()

    async def _connect_forever(self):
        while not self._stop_event.is_set():
            try:
                async with websockets.connect(WS_SERVER_URL) as ws:
                    print(f"[WS] Connected to {WS_SERVER_URL}")
                    await ws.send("Hello from DOOM")
                    async for message in ws:
                        self._handle_message(message)
                        if self._stop_event.is_set():
                            break
            except OSError as e:
                print(f"[WS] Connection failed ({e}), retrying in {RECONNECT_DELAY}s...")
            except websockets.ConnectionClosed:
                print(f"[WS] Connection closed, retrying in {RECONNECT_DELAY}s...")

            if not self._stop_event.is_set():
                await asyncio.sleep(RECONNECT_DELAY)

        print("[WS] Client stopped.")
