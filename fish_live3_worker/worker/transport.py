"""Fish's documented LiveKit protocol for turn-taking HA satellites.

This is deliberately not described as full duplex: stock Assist satellites
provide a transcribed turn and play the resulting audio afterwards.
"""

from __future__ import annotations

import asyncio
import contextlib
import io
import json
import logging
import time
import wave
from array import array
from collections import OrderedDict

from livekit import rtc


def trim_wait_silence(pcm):
    """Keep speech padding while omitting silence collected during inference."""
    samples = array("h", pcm)
    voiced = [
        start
        for start in range(0, len(samples), 480)
        if max((abs(value) for value in samples[start : start + 480]), default=0) > 200
    ]
    if not voiced:
        return bytes(pcm)
    return samples[max(0, voiced[0] - 2400) : min(len(samples), voiced[-1] + 480 + 4800)].tobytes()


class WorkerTurn:
    def __init__(self, bridge, token):
        self.bridge, self.token = bridge, token
        self.context = self.device_id = None
        self.room = rtc.Room()
        self.fish_id = None
        self.lock = asyncio.Lock()
        self.parts = OrderedDict()
        self.pcm = bytearray()
        self.pending = None
        self.mode = "initializing"
        self.connected = False
        self.last_used = time.monotonic()
        self.changed = 0.0
        self.tasks = set()
        self._settler = None
        self._ready = asyncio.Event()

    def task(self, coroutine):
        item = self.bridge.hass.async_create_task(coroutine)
        self.tasks.add(item)
        item.add_done_callback(self.tasks.discard)
        return item

    async def connect(self):
        @self.room.on("data_received")
        def on_data(packet):
            if packet.topic != "agent-event":
                return
            try:
                event = json.loads(packet.data)
            except (ValueError, UnicodeError):
                return
            if event.get("type") == "client_tool.call":
                self.task(self.run_tool(event))
            elif event.get("type") == "session.ended":
                self.connected = False
                if self.pending and not self.pending.done() and not self.parts:
                    self.pending.set_exception(RuntimeError("Fish ended the session"))

        @self.room.on("participant_connected")
        def participant_connected(participant):
            if participant.kind == rtc.ParticipantKind.PARTICIPANT_KIND_AGENT:
                self._ready.set()

        @self.room.on("participant_attributes_changed")
        def attributes_changed(changed, participant):
            if "lk.agent.state" in changed:
                self.mode = changed["lk.agent.state"]
                self._ready.set()
                self.schedule_settle()

        @self.room.on("track_subscribed")
        def track_subscribed(track, publication, participant):
            if track.kind == rtc.TrackKind.KIND_AUDIO:
                self.task(self.read_audio(track))

        self.room.register_text_stream_handler(
            "lk.transcription", lambda reader, identity: self.task(self.read_text(reader, identity))
        )
        token = self.token
        self.fish_id = token["session_id"]
        if token.get("transport") != "livekit":
            await self.close()
            raise RuntimeError("Unsupported Fish realtime transport")
        try:
            await self.room.connect(token["livekit_url"], token["token"])
            self.connected = True
            for participant in self.room.remote_participants.values():
                if participant.kind == rtc.ParticipantKind.PARTICIPANT_KIND_AGENT:
                    self._ready.set()
            await asyncio.wait_for(self._ready.wait(), 20)
        except Exception:
            await self.close()
            raise

    async def read_text(self, reader, participant_identity):
        if participant_identity == self.room.local_participant.identity:
            return
        text = await reader.read_all()
        if self.pending and not self.pending.done() and text.strip():
            segment = (reader.info.attributes or {}).get("lk.segment_id", reader.info.stream_id)
            self.parts[segment] = text
            self.changed = time.monotonic()
            self.schedule_settle()

    async def read_audio(self, track):
        stream = rtc.AudioStream(track, sample_rate=24000, num_channels=1)
        try:
            async for event in stream:
                if self.pending and not self.pending.done():
                    if len(self.pcm) > 24000 * 2 * 120:
                        self.pending.set_exception(RuntimeError("Fish reply exceeded two minutes"))
                    else:
                        self.pcm.extend(bytes(event.frame.data))
        finally:
            await stream.aclose()

    def schedule_settle(self):
        if self._settler:
            self._settler.cancel()
        self._settler = self.task(self.settle())

    async def settle(self):
        await asyncio.sleep(0.8)
        if (
            self.pending
            and not self.pending.done()
            and self.parts
            and self.mode not in ("thinking", "speaking")
            and time.monotonic() - self.changed >= 0.75
        ):
            text = " ".join(value.strip() for value in self.parts.values())
            buffer = io.BytesIO()
            with wave.open(buffer, "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(24000)
                wav.writeframes(trim_wait_silence(self.pcm))
            self.pending.set_result((text, buffer.getvalue()))

    async def send(self, event):
        await self.room.local_participant.publish_data(
            json.dumps(event).encode(), reliable=True, topic="client-event"
        )

    async def run_tool(self, event):
        try:
            result = await self.bridge.tool(
                event.get("toolName"), event.get("params", {}), self.context, self.device_id
            )
            payload = {"type": "client_tool.result", "callId": event["callId"], "result": result}
        except Exception as error:
            logging.warning("Home tool failed: %s", type(error).__name__)
            payload = {
                "type": "client_tool.result",
                "callId": event["callId"],
                "isError": True,
                "result": {"error": "Home Assistant could not complete that request"},
            }
        await self.send(payload)

    async def reply(self, text):
        async with self.lock:
            if not self.connected:
                await self.connect()
            self.parts.clear()
            self.pcm.clear()
            self.pending = asyncio.get_running_loop().create_future()
            self.last_used = time.monotonic()
            try:
                await self.send({"type": "user.message", "text": text, "audio": True})
                result = await asyncio.wait_for(self.pending, 90)
                return result
            except Exception:
                await self.close()
                raise
            finally:
                self.pending = None

    async def close(self):
        self.connected = False
        for task in list(self.tasks):
            if task is not asyncio.current_task():
                task.cancel()
        if self.fish_id:
            fish_id, self.fish_id = self.fish_id, None
            with contextlib.suppress(Exception):
                await self.bridge.end_upstream(fish_id)
        with contextlib.suppress(Exception):
            await self.room.disconnect()
