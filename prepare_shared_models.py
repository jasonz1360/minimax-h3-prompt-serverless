"""Download and verify the pinned H3 model files on a mounted network volume."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-root", default="/workspace/models")
    parser.add_argument("--manifest", default=str(Path(__file__).with_name("model-manifest.json")))
    args = parser.parse_args()
    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    root = Path(args.model_root)
    root.mkdir(parents=True, exist_ok=True)
    aria2 = shutil.which("aria2c")
    if not aria2:
        raise SystemExit("Install aria2 before running this downloader")

    for item in manifest["files"]:
        target = root / item["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.is_file() and target.stat().st_size == item["size"]:
            with target.open("rb") as source:
                digest = hashlib.file_digest(source, "sha256").hexdigest()
            if digest == item["sha256"]:
                print(f"MODEL_VERIFIED {item['path']}", flush=True)
                continue

        url = (
            f"https://huggingface.co/{manifest['repository']}/resolve/"
            f"{manifest['revision']}/{item['path']}"
        )
        print(f"MODEL_DOWNLOAD {item['path']} bytes={item['size']}", flush=True)
        subprocess.run(
            [
                aria2,
                "--continue=true",
                "--max-connection-per-server=8",
                "--split=8",
                "--min-split-size=64M",
                "--file-allocation=none",
                "--max-tries=10",
                "--retry-wait=5",
                "--auto-file-renaming=false",
                "--allow-overwrite=true",
                "--check-integrity=true",
                f"--checksum=sha-256={item['sha256']}",
                "--console-log-level=warn",
                "--summary-interval=30",
                "--dir", str(target.parent),
                "--out", target.name,
                url,
            ],
            check=True,
        )
        if target.stat().st_size != item["size"]:
            raise RuntimeError(f"Unexpected file size: {item['path']}")
        print(f"MODEL_VERIFIED {item['path']}", flush=True)

    (root / "h3-models-ready.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print("MODEL_PRELOAD_COMPLETE", flush=True)


if __name__ == "__main__":
    main()
