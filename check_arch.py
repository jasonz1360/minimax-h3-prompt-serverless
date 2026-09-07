"""Build-time guard: assert the installed torch actually carries kernels for the GPUs
we deploy on. Runs on a CPU-only builder, so it cannot use torch.cuda.get_arch_list()
(that returns [] without a device) — it scans the compiled library instead.

Usage: python check_arch.py sm_90 sm_120
"""
import pathlib
import re
import sys

import torch

CHUNK = 32 * 1024 * 1024


def compiled_archs():
    lib_dir = pathlib.Path(torch.__file__).parent / "lib"
    libs = sorted(lib_dir.glob("libtorch_cuda*.so")) + sorted(lib_dir.glob("libtorch_cuda*.so.*"))
    if not libs:
        sys.exit(f"no libtorch_cuda found under {lib_dir}")
    found = set()
    pattern = re.compile(rb"sm_(\d{2,3})[af]?")
    for lib in libs:
        with lib.open("rb") as fh:
            tail = b""
            while True:
                block = fh.read(CHUNK)
                if not block:
                    break
                for m in pattern.finditer(tail + block):
                    found.add(f"sm_{m.group(1).decode()}")
                tail = block[-16:]  # carry a boundary so split matches still hit
    return found, [str(p.name) for p in libs]


def main():
    required = sys.argv[1:] or ["sm_90"]
    version = torch.__version__
    print(f"torch: {version}, cuda: {torch.version.cuda}")
    archs, libs = compiled_archs()
    print(f"scanned: {', '.join(libs)}")
    print(f"compiled archs: {' '.join(sorted(archs, key=lambda a: int(a[3:])))}")
    missing = [a for a in required if a not in archs]
    if missing:
        sys.exit(f"FAIL: torch {version} has no kernels for {', '.join(missing)} — "
                 "it would die with CUDA error 209 on that hardware")
    print(f"OK: kernels present for {', '.join(required)}")


if __name__ == "__main__":
    main()
