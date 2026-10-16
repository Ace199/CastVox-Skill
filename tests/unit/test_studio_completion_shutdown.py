import json
from unittest.mock import Mock, patch
import unittest

from studio_v16_server import Handler


class CompletionShutdown(unittest.TestCase):
    def test_saved_answer_still_closes_once_server_when_browser_response_fails(self):
        handler = object.__new__(Handler)
        handler.path = '/api/v16/answers'
        body = json.dumps({'question_id': 'q_fixture', 'assignments': {'r': 'pv_fixture'}}).encode()
        import io
        handler.rfile = io.BytesIO(body)
        handler.headers = {'Content-Length': str(len(body)), 'Content-Type': 'application/json'}
        handler.server = Mock(question_id='q_fixture', close_after_answer=True)
        handler.server.backend.dispatch.return_value = {'answer_id': 'a_fixture'}
        handler._guard = Mock()
        handler._json = Mock(side_effect=BrokenPipeError)
        handler._failure = Mock()
        with patch('makesound.harness_resume.notify', return_value={'status': 'delivered'}) as notify, \
                patch('studio_v16_server.threading.Thread') as thread:
            Handler.do_POST(handler)
            handler.server.backend.dispatch.assert_called_once()
            notify.assert_called_once()
            thread.assert_called_once()
            self.assertEqual(thread.call_args.kwargs['target'], handler.server.shutdown)
            thread.return_value.start.assert_called_once()


if __name__ == '__main__':
    unittest.main()
