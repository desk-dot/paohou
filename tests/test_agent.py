import unittest
from agent import review_run
from model_client import ModelClient, ModelError, extract_record


class FakeClient:
    model = "test-double-not-real-model"

    def __init__(self, responses):
        self.responses = iter(responses)
        self.messages = []

    def chat(self, messages, tools=None):
        self.messages.append(list(messages))
        return next(self.responses)


def tool_call(name="analyze_run", arguments="{}"):
    return {"role": "assistant", "content": None, "tool_calls": [
        {"id": "call_1", "type": "function", "function": {"name": name, "arguments": arguments}}]}


class AgentTests(unittest.TestCase):
    def test_calls_metrics_before_review(self):
        client = FakeClient([tool_call(), {"content": "结果为 6:00 /km"}])
        review, trace = review_run(client, {"total_distance_km": 5, "total_duration_s": 1800})
        self.assertIn("6:00", review)
        self.assertEqual(trace[1]["result"]["average_pace"], "6:00")
        self.assertEqual(client.messages[1][-1]["role"], "tool")

    def test_ungrounded_answers_reach_limit(self):
        client = FakeClient([{"content": "无需工具"}] * 4)
        with self.assertRaises(ModelError):
            review_run(client, {"total_distance_km": 5, "total_duration_s": 1800})
        self.assertEqual(len(client.messages), 4)

    def test_unknown_tool_cannot_execute(self):
        client = FakeClient([tool_call("run_shell"), tool_call(), {"content": "复盘"}])
        _, trace = review_run(client, {"total_distance_km": 5, "total_duration_s": 1800})
        self.assertEqual(trace[1]["status"], "rejected")

    def test_invalid_tool_arguments(self):
        client = FakeClient([tool_call(arguments="not json")])
        with self.assertRaises(ModelError):
            review_run(client, {"total_distance_km": 5, "total_duration_s": 1800})

    def test_extraction_fences_and_missing_values(self):
        client = FakeClient([{"content": '```json\n{"splits": [], "total_distance_km": null}\n```'}])
        result = extract_record(client, [(b"test-image", "image/png")])
        self.assertIsNone(result["total_distance_km"])

    def test_bad_extraction_is_reported(self):
        with self.assertRaises(ModelError):
            extract_record(FakeClient([{"content": "无法识别"}]), [(b"test", "image/png")])

    def test_config_rejects_insecure_url(self):
        for url in ["", "http://example.com/v1", "https://user:key@example.com/v1"]:
            with self.assertRaises(ModelError):
                ModelClient(url, "dummy-key", "dummy-model")


if __name__ == "__main__":
    unittest.main()
