"""Rebuild narration timing, subtitles and the HyperFrames project from the
current per-slide metadata.json files (after element re-segmentation)."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generate_hyperframes_video_project import (  # noqa: E402
    OUT,
    write_narration_and_timing,
    write_hyperframes_files,
)


def load_metadatas():
    metadatas = []
    for n in range(1, 21):
        path = OUT / f"slide_{n:02d}" / "metadata.json"
        metadatas.append(json.loads(path.read_text(encoding="utf-8")))
    return metadatas


def main():
    metadatas = load_metadatas()
    timing = write_narration_and_timing(metadatas)
    write_hyperframes_files(metadatas, timing)
    total = max(t["end"] for t in timing.values())
    layers = sum(len(m["layers"]) for m in metadatas)
    print(f"timeline rebuilt: {layers} layers, narration ends at {total}s")


if __name__ == "__main__":
    main()
