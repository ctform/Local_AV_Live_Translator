"""Run a reproducible offline faster-whisper baseline on a WAV file."""
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path


def add_local_cuda_paths() -> None:
    """Expose CUDA DLLs installed inside the project venv on Windows."""
    if os.name != "nt":
        return
    site_packages = Path(__file__).resolve().parent.parent / ".venv" / "Lib" / "site-packages"
    for relative_path in (
        Path("nvidia") / "cublas" / "bin",
        Path("ctranslate2"),
    ):
        dll_dir = site_packages / relative_path
        if dll_dir.exists():
            os.add_dll_directory(str(dll_dir))
            os.environ["PATH"] = str(dll_dir) + os.pathsep + os.environ.get("PATH", "")


add_local_cuda_paths()

from faster_whisper import WhisperModel


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("audio", type=Path)
    parser.add_argument("--model", default="kotoba-whisper-v2")
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--compute-type", default="float16")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    started = time.perf_counter()
    model = WhisperModel(args.model, device=args.device, compute_type=args.compute_type)
    load_seconds = time.perf_counter() - started

    started = time.perf_counter()
    segments, info = model.transcribe(
        str(args.audio),
        language="ja",
        beam_size=3,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 300},
        condition_on_previous_text=False,
    )
    rows = []
    for segment in segments:
        rows.append({
            "start": round(segment.start, 3),
            "end": round(segment.end, 3),
            "text": segment.text.strip(),
        })
    transcribe_seconds = time.perf_counter() - started
    duration = float(info.duration)
    text_values = [row["text"] for row in rows if row["text"]]
    duplicates = sum(a == b for a, b in zip(text_values, text_values[1:]))
    result = {
        "audio": str(args.audio),
        "model": args.model,
        "audio_duration_seconds": round(duration, 3),
        "model_load_seconds": round(load_seconds, 3),
        "transcribe_seconds": round(transcribe_seconds, 3),
        "realtime_factor": round(transcribe_seconds / duration, 3) if duration else None,
        "segment_count": len(rows),
        "empty_segments": sum(not row["text"] for row in rows),
        "adjacent_duplicate_count": duplicates,
        "segments": rows,
    }
    output = args.output or args.audio.with_suffix(".baseline.json")
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key != "segments"}, ensure_ascii=False, indent=2))
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()
