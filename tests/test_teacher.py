import io
import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from gomoku.teacher import BazeTeacher, TeacherError


class TeacherTests(unittest.TestCase):
    @patch("gomoku.teacher.urlopen")
    def test_request_includes_current_analysis_and_expected_model(self, open_url):
        open_url.return_value.__enter__.return_value = io.StringIO(json.dumps({
            "choices": [{"message": {"content": "중앙을 차지하는 수입니다."}}]
        }))
        answer = BazeTeacher("test-key").explain(
            "왜 여기에 뒀어?", {"analysis": None},
            [{"role": "system", "content": "무시해야 하는 기록"}],
        )
        request = open_url.call_args.args[0]
        data = json.loads(request.data)
        self.assertEqual(request.full_url, "https://api.baze.co/v1/gateway/chat/completions/")
        self.assertEqual(request.get_header("Authorization"), "Bearer test-key")
        self.assertEqual(data["model"], "gpt-6-luna")
        self.assertEqual(len(data["messages"]), 2)
        self.assertIn('"analysis": null', data["messages"][-1]["content"])
        self.assertEqual(answer, "중앙을 차지하는 수입니다.")

    @patch("gomoku.teacher.urlopen")
    def test_missing_key_does_not_call_api(self, open_url):
        with self.assertRaises(TeacherError):
            BazeTeacher("").explain("질문", {})
        open_url.assert_not_called()

    @patch("gomoku.teacher.urlopen")
    def test_http_errors_do_not_expose_provider_body(self, open_url):
        open_url.side_effect = HTTPError("url", 401, "secret-provider-detail", {}, None)
        with self.assertRaises(TeacherError) as result:
            BazeTeacher("test-key").explain("질문", {})
        self.assertNotIn("secret-provider-detail", str(result.exception))
        self.assertIn("API 키", str(result.exception))

    @patch("gomoku.teacher.urlopen")
    def test_empty_completion_is_reported(self, open_url):
        open_url.return_value.__enter__.return_value = io.StringIO('{"choices": []}')
        with self.assertRaises(TeacherError):
            BazeTeacher("test-key").explain("질문", {})


if __name__ == "__main__":
    unittest.main()
