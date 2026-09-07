import json
import unittest

from h3_prompt_adapter import adapt_job


class PromptAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open("example_workflows/t2v_api.json", encoding="utf-8") as source:
            cls.workflow = json.load(source)

    def test_prompt_builds_default_workflow(self):
        job = {"input": {"prompt": "A quiet lake", "seed": 7}}
        adapted = adapt_job(job, self.workflow)
        self.assertEqual(adapted["input"]["workflow"]["cond"]["inputs"]["prompt"], "A quiet lake")
        self.assertEqual(adapted["input"]["workflow"]["noise"]["inputs"]["noise_seed"], 7)
        self.assertNotIn("workflow", job["input"])

    def test_full_workflow_is_unchanged(self):
        job = {"input": {"workflow": {"custom": True}}}
        self.assertIs(adapt_job(job, self.workflow), job)


if __name__ == "__main__":
    unittest.main()
