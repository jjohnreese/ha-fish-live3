"""Exercise actual SDK transcript metadata without joining a room."""

import asyncio
import importlib.util
from array import array
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from livekit import rtc

path = Path(__file__).resolve().parent.parent / "fish_live3_worker/worker/transport.py"
spec = importlib.util.spec_from_file_location("worker_transport", path)
transport = importlib.util.module_from_spec(spec)
spec.loader.exec_module(transport)


def test_sdk_stream_metadata_and_missing_attributes():
    async def run():
        original = transport.rtc.Room
        transport.rtc.Room = lambda: SimpleNamespace(
            local_participant=SimpleNamespace(identity="local")
        )
        try:
            for attributes in (None, {}, {"lk.segment_id": "segment-1"}):
                turn = transport.WorkerTurn(None, {})
                turn.pending = asyncio.get_running_loop().create_future()
                turn.schedule_settle = lambda: None
                reader = SimpleNamespace(
                    info=rtc.TextStreamInfo(
                        stream_id="stream-1",
                        mime_type="text/plain",
                        topic="lk.transcription",
                        timestamp=0,
                        size=None,
                        attributes=attributes,
                        attachments=[],
                    ),
                    read_all=AsyncMock(return_value="Hello!"),
                )
                await turn.read_text(reader, "agent")
                assert list(turn.parts.values()) == ["Hello!"]
                assert list(turn.parts) == ["segment-1" if attributes else "stream-1"]
                turn.parts.clear()
                await turn.read_text(reader, "local")
                assert not turn.parts
        finally:
            transport.rtc.Room = original

    asyncio.run(run())


def test_wait_silence_removed_with_speech_padding():
    silence = array("h", [0] * 24000)
    speech = array("h", [1200, -1200] * 12000)
    trimmed = array("h", transport.trim_wait_silence((silence + speech + silence).tobytes()))
    assert len(trimmed) == 2400 + 24000 + 4800
    assert trimmed[2400:26400] == speech
    quiet = array("h", [80, -80] * 12000).tobytes()
    assert transport.trim_wait_silence(quiet) == quiet
