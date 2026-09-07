"""Runpod handler that adds a prompt-only interface to worker-comfyui."""

import importlib.util
import json

import runpod

from h3_prompt_adapter import adapt_job


with open("/opt/minimax-h3/t2v_api.json", encoding="utf-8") as workflow_file:
    DEFAULT_WORKFLOW = json.load(workflow_file)

spec = importlib.util.spec_from_file_location("worker_comfyui_handler", "/handler_base.py")
worker_comfyui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker_comfyui)


def handler(job):
    return worker_comfyui.handler(adapt_job(job, DEFAULT_WORKFLOW))


if __name__ == "__main__":
    runpod.serverless.start({"handler": handler})
