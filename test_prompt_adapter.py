import json
import unittest

from h3_prompt_adapter import adapt_job


class PromptAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open("example_workflows/t2v_api.json", encoding="utf-8") as source:
            cls.workflow = json.load(source)

    def test_prompt_builds_default_workflow(self):
        job = {"input": {"prompt": "A quiet lake", "seed": 7, "steps": 16}}
        adapted = adapt_job(job, self.workflow)
        self.assertEqual(adapted["input"]["workflow"]["cond"]["inputs"]["prompt"], "A quiet lake")
        self.assertEqual(adapted["input"]["workflow"]["noise"]["inputs"]["noise_seed"], 7)
        self.assertEqual(adapted["input"]["workflow"]["sigmas"]["inputs"]["steps"], 16)
        self.assertNotIn("workflow", job["input"])

    def test_native_high_resolution_is_supported(self):
        job = {"input": {"prompt": "A wide shot", "width": 1344, "height": 768}}
        adapted = adapt_job(job, self.workflow)
        cond = adapted["input"]["workflow"]["cond"]["inputs"]
        self.assertEqual((cond["width"], cond["height"]), (1344, 768))

    def test_oversized_canvas_is_rejected(self):
        job = {"input": {"prompt": "Too large", "width": 1344, "height": 800}}
        with self.assertRaisesRegex(ValueError, "exceeds the MiniMax H3 maximum area"):
            adapt_job(job, self.workflow)

    def test_dimensions_must_be_multiples_of_32(self):
        job = {"input": {"prompt": "Invalid", "width": 1000, "height": 576}}
        with self.assertRaisesRegex(ValueError, "multiple of 32"):
            adapt_job(job, self.workflow)

    def test_steps_are_bounded(self):
        for steps in (0, 51):
            with self.subTest(steps=steps):
                job = {"input": {"prompt": "Invalid", "steps": steps}}
                with self.assertRaisesRegex(ValueError, "between 1 and 50"):
                    adapt_job(job, self.workflow)

    def test_first_and_last_frames_are_added_to_workflow(self):
        job = {
            "input": {
                "prompt": "Move between these frames",
                "first_frame": "data:image/png;base64,FIRST",
                "last_frame": "data:image/png;base64,LAST",
            }
        }
        adapted = adapt_job(job, self.workflow)
        workflow = adapted["input"]["workflow"]
        self.assertEqual(workflow["cond"]["inputs"]["first_frame"], ["load_first_frame", 0])
        self.assertEqual(workflow["cond"]["inputs"]["last_frame"], ["load_last_frame", 0])
        self.assertEqual(
            [image["name"] for image in adapted["input"]["images"]],
            ["reelmake_first_frame.png", "reelmake_last_frame.png"],
        )

    def test_full_workflow_is_unchanged(self):
        job = {"input": {"workflow": {"custom": True}}}
        self.assertIs(adapt_job(job, self.workflow), job)


if __name__ == "__main__":
    unittest.main()
