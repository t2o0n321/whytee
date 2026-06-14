"""Audio chunking/cleanup tests — ffmpeg is faked, no real binary/network."""

from __future__ import annotations

import os

from app.providers import audio


def _fake_ffmpeg_factory(num_chunks: int):
    """Return a fake subprocess.run that 'emits' num_chunks chunk files.

    It parses the output pattern (``..._chunk_%03d.wav``) from the argv and
    writes that many files, mimicking ffmpeg's segment muxer.
    """

    def fake_run(argv, check=True):
        pattern = next(a for a in argv if a.endswith("_chunk_%03d.wav"))
        base = pattern.replace("_chunk_%03d.wav", "")
        for i in range(num_chunks):
            with open(f"{base}_chunk_{i:03d}.wav", "w") as fh:
                fh.write("x")
        return None

    return fake_run


def test_split_audio_returns_ordered_offsets(monkeypatch, tmp_path):
    monkeypatch.setattr(audio.subprocess, "run", _fake_ffmpeg_factory(3))
    wav = tmp_path / "vid.wav"
    wav.write_text("x")

    chunks = audio.split_audio(str(wav), chunk_seconds=900)

    assert [c.offset_s for c in chunks] == [0, 900, 1800]
    assert all(c.path.endswith(".wav") for c in chunks)


def test_split_audio_removes_stale_chunks_first(monkeypatch, tmp_path):
    # A previous, longer run left 5 chunks behind...
    base = tmp_path / "vid"
    for i in range(5):
        (tmp_path / f"vid_chunk_{i:03d}.wav").write_text("stale")
    wav = tmp_path / "vid.wav"
    wav.write_text("x")

    # ...this run only produces 2. The stale 3 must not be stitched in.
    monkeypatch.setattr(audio.subprocess, "run", _fake_ffmpeg_factory(2))
    chunks = audio.split_audio(str(wav), chunk_seconds=900)

    assert len(chunks) == 2
    assert not os.path.exists(f"{base}_chunk_002.wav")


def test_cleanup_video_removes_audio_and_chunks(tmp_path):
    vid = "dQw4w9WgXcQ"
    (tmp_path / f"{vid}.wav").write_text("x")
    (tmp_path / f"{vid}.webm").write_text("x")  # yt-dlp intermediate
    (tmp_path / f"{vid}_chunk_000.wav").write_text("x")
    (tmp_path / f"{vid}_chunk_001.wav").write_text("x")
    # A different video's files must survive.
    (tmp_path / "OTHERvideo1.wav").write_text("keep")

    audio.cleanup_video(str(tmp_path), vid)

    remaining = sorted(os.listdir(tmp_path))
    assert remaining == ["OTHERvideo1.wav"]
