"""Convert a simple MiniMax H3 prompt request into a ComfyUI API workflow."""

from copy import deepcopy


MIN_DIMENSION = 256
MAX_DIMENSION = 1344
MAX_PIXELS = 1344 * 768
MIN_STEPS = 1
MAX_STEPS = 50


def _as_int(job_input, field):
    value = job_input[field]
    if isinstance(value, bool):
        raise ValueError(f"'{field}' must be an integer")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"'{field}' must be an integer") from exc


def _validate_dimensions(width, height):
    for field, value in (("width", width), ("height", height)):
        if not MIN_DIMENSION <= value <= MAX_DIMENSION:
            raise ValueError(
                f"'{field}' must be between {MIN_DIMENSION} and {MAX_DIMENSION}"
            )
        if value % 32:
            raise ValueError(f"'{field}' must be a multiple of 32")

    if width * height > MAX_PIXELS:
        raise ValueError(
            f"requested canvas {width}x{height} exceeds the MiniMax H3 maximum "
            f"area of {MAX_PIXELS} pixels (1344x768)"
        )


def _add_frame(workflow, adapted_input, field, image_data):
    if not isinstance(image_data, str) or not image_data.strip():
        raise ValueError(f"'{field}' must be a base64 image or data URI")

    filename = f"reelmake_{field}.png"
    workflow[f"load_{field}"] = {
        "class_type": "LoadImage",
        "inputs": {"image": filename},
    }
    workflow["cond"]["inputs"][field] = [f"load_{field}", 0]
    adapted_input.setdefault("images", []).append(
        {"name": filename, "image": image_data.strip()}
    )


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

    width = _as_int(job_input, "width") if "width" in job_input else int(cond["width"])
    height = _as_int(job_input, "height") if "height" in job_input else int(cond["height"])
    _validate_dimensions(width, height)
    cond["width"] = width
    cond["height"] = height

    if "length" in job_input:
        cond["length"] = _as_int(job_input, "length")

    if "seed" in job_input:
        workflow["noise"]["inputs"]["noise_seed"] = _as_int(job_input, "seed")

    if "steps" in job_input:
        steps = _as_int(job_input, "steps")
        if not MIN_STEPS <= steps <= MAX_STEPS:
            raise ValueError(f"'steps' must be between {MIN_STEPS} and {MAX_STEPS}")
        workflow["sigmas"]["inputs"]["steps"] = steps

    adapted = deepcopy(job)
    adapted["input"]["workflow"] = workflow
    for field in ("first_frame", "last_frame"):
        if field in job_input:
            _add_frame(workflow, adapted["input"], field, job_input[field])
    return adapted
