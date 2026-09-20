import json
import tempfile
import unittest
from pathlib import Path

from classify_surroundings import DEFAULT_IMAGE, bytes_data_url, data_url, extract_json, load_lidar
from yibu_audit import append_audit_record


class ClassificationTests(unittest.TestCase):
    def test_bundled_image_encodes_as_jpeg_data_url(self):
        encoded = data_url(DEFAULT_IMAGE)
        self.assertTrue(encoded.startswith("data:image/jpeg;base64,"))
        self.assertGreater(len(encoded), 100)
        self.assertEqual(bytes_data_url(b"abc"), "data:image/jpeg;base64,YWJj")

    def test_lidar_object_and_fenced_model_json(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "lidar.json"
            path.write_text(json.dumps({"ranges": [1.0, None, 2.5]}), encoding="utf-8")
            self.assertEqual(load_lidar(path)["ranges"], [1.0, None, 2.5])
        self.assertEqual(extract_json("```json\n{\"scene_type\":\"hallway\"}\n```"),
                         {"scene_type": "hallway"})

    def test_audit_log_excludes_key_and_response_content(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "calls.jsonl"
            append_audit_record(
                model="qwen3.5-omni-plus", api_key="secret-1234",
                endpoint="https://example.test/v1/chat/completions", purpose="test",
                transport="http", ok=True, latency_s=0.2,
                response_json={"usage": {"prompt_tokens": 10, "completion_tokens": 2},
                               "choices": [{"message": {"content": "private"}}]},
                audit_log=path,
            )
            text = path.read_text(encoding="utf-8")
            record = json.loads(text)
            self.assertNotIn("secret-1234", text)
            self.assertNotIn("private", text)
            self.assertEqual(record["key_suffix"], "...1234")
            self.assertEqual(record["total_tokens"], 12)


if __name__ == "__main__":
    unittest.main()
