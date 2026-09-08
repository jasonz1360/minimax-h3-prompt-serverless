# minimax-h3-comfyui-serverless

## Prompt-friendly Runpod image

This fork adds a prompt-only request interface while preserving the original
`input.workflow` API. The published image is:

`ghcr.io/jasonz1360/minimax-h3-prompt-serverless:v1.0.0`

Minimal request:

```json
{
  "input": {
    "prompt": "A cinematic corgi surfing at golden hour",
    "seed": 42
  }
}
```

Optional prompt-mode fields are `width`, `height`, `length`, `seed`, `steps`,
`first_frame`, and `last_frame`.
Defaults come from `example_workflows/t2v_api.json`: 1344×768, 124 frames,
seed 42, and 20 steps. Width and height must be multiples of 32, each must be
between 256 and 1344, and the canvas area cannot exceed 1344×768. Frame values
are base64 strings or data URIs. Supplying `input.workflow` bypasses the adapter
unchanged.

MiniMax H3 (Hailuo 3.0) video+audio generation as a RunPod serverless worker.
Sister repo of [krea2-comfyui-serverless](https://github.com/vincezh2000/krea2-comfyui-serverless), same pattern:
`runpod/worker-comfyui` base, weights baked into the image, GHA builds → ghcr.

**Image:** `ghcr.io/vincezh2000/minimax-h3-comfyui-serverless:latest`

## What's inside

- Base: `runpod/worker-comfyui:5.8.6-base`, ComfyUI pinned to **v0.30.1** (native H3 nodes need ≥0.30.0)
- Weights (ComfyUI-recommended pruned int8 set, 42.5 GB total, from [Comfy-Org/MiniMax-H3](https://huggingface.co/Comfy-Org/MiniMax-H3)):
  - `minimax_h3_fl2va_pruned_int8_convrot.safetensors` (21 GB) — covers **T2V and first/last-frame I2V**
  - `qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors` (15.7 GB) — text encoder
  - `minimax_h3_video_vae_fp16.safetensors` (5.2 GB) + `minimax_h3_audio_vae_fp32.safetensors` (0.6 GB)
- NOT included: `ref2va` model (reference-to-video, another 21 GB). Add a fourth aria2 RUN in the Dockerfile if needed.

Model capabilities: up to ~15s at 24 FPS with **native stereo audio** (speech/SFX/music generated in the same pass),
768px-short-edge canvas (max 768×1344 px area), aspect ratios from 21:9 to 9:16.

## RunPod endpoint settings

| Setting | Value |
|---|---|
| Container image | `ghcr.io/vincezh2000/minimax-h3-comfyui-serverless:latest` |
| GPU | 80 GB (A100/H100) recommended; 48 GB (L40S/A6000) works for 768p with offloading |
| Container disk | **≥ 100 GB** (image unpacks to ~55 GB) |
| FlashBoot | on |
| Env (optional) | `BUCKET_ENDPOINT_URL` etc. for S3 output upload — without it results return as base64 |

First cold pull of the ~50 GB image takes a while; subsequent starts on a cached host are fast.

## Calling it

`SaveVideo` results are collected by worker-comfyui like images (mp4 in, base64/S3 out — verified: the
history output key is `images`).

```bash
curl -s -X POST "https://api.runpod.ai/v2/<ENDPOINT_ID>/run" \
  -H "Authorization: Bearer $RUNPOD_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{\"input\": {\"workflow\": $(cat example_workflows/t2v_api.json)}}"
```

The example workflow mirrors the official ComfyUI T2V template: `res_multistep` sampler, `simple` scheduler,
20 steps, `BasicGuider` (no CFG / no negative), dual VAE decode (video + audio) → `CreateVideo` (24 fps) → `SaveVideo`.

Knobs in `example_workflows/t2v_api.json`:

- **prompt** — describe shots, camera, and the audio (dialogue/SFX/music) in one block
- **width/height** — 32-multiples, area capped at 768×1344 (1344×768 = 16:9 max)
- **length** — frame count at 24 fps on the model's 17k+5 grid: 124 ≈ 5s, 243 ≈ 10s, 362 ≈ 15s
  (invalid values snap up automatically)
- **steps** — 1–50 sampling steps; 20 is the reference-quality default, 16 is the
  balanced preset, and 12 is suitable for faster previews
- **first_frame/last_frame** — optional base64 image strings or data URIs. The
  adapter uploads them and connects the required `LoadImage` nodes automatically

## Build pipeline

Push to `Dockerfile` or `build.yml` → GHA builds and pushes to ghcr.

Two-phase build (the naive single Dockerfile OOMs the runner disk — buildkit's export step needs
~2x the 42.5 GB of weight content):

1. `docker build` a slim **:code** image (base + ComfyUI v0.30.1 pin, no weights) and push it
2. For each weight file: download → tar → **`crane append`** streams it onto the remote image as a
   new layer (peak disk = one file + its tar, on /mnt) → final manifest tagged **:latest**
