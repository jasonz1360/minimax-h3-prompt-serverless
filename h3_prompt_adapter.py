"""Convert a simple MiniMax H3 prompt request into a ComfyUI API workflow."""

from copy import deepcopy


def adapt_job(job, default_workflow):
    """Return a job accepted by worker-comfyui, preserving full workflows."""
    if not isinstance(job, dict) or not isinstance(job.get("input"), dict):
        return job

    job_input = job["input"]
    if job_input.get("workflow") is not None:
        return job

    prompt = job_input.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        return job

    workflow = deepcopy(default_workflow)
    cond = workflow["cond"]["inputs"]
    cond["prompt"] = prompt.strip()

    for field in ("width", "height", "length"):
        if field in job_input:
            cond[field] = int(job_input[field])

    if "seed" in job_input:
        workflow["noise"]["inputs"]["noise_seed"] = int(job_input["seed"])

    adapted = deepcopy(job)
    adapted["input"]["workflow"] = workflow
    return adapted
