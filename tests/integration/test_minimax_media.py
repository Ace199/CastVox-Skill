import copy
import hashlib
import io
import json
import unittest
import wave
from unittest.mock import patch

from tests.helpers import Fixture
from tests.unit.test_v16 import SOURCE
from makesound.core_v16 import ProjectCore
from makesound.errors import MakeSoundError
from makesound.generation import Generation
from makesound.media import MediaTools
from makesound.minimax_provider import MiniMaxProvider, HTTPSMiniMaxTransport, normalize_subtitles
from makesound.production import plan, repair_subtitles, main as production_main
from makesound.providers import duration
from makesound.storage import atomic_write, read_json


REAL = {**SOURCE, 'provider': 'minimax', 'region': 'cn', 'model': 'speech-2.8-hd'}


def wav_bytes(seconds=6, rate=32000):
    buffer = io.BytesIO()
    with wave.open(buffer, 'wb') as audio:
        audio.setnchannels(1); audio.setsampwidth(2); audio.setframerate(rate)
        audio.writeframes(b'\x00\x00' * round(seconds * rate))
    return buffer.getvalue()


class StubTransport:
    def __init__(self):
        self.requests = []
        self.response = {'base_resp': {'status_code': 0}, 'data': {'status': 2, 'audio': wav_bytes().hex(),
                        'subtitle_file': 'https://subtitles.example.test/sentence.json'}}
        self.timing = [{'text': '原文。', 'time_begin': 100, 'time_end': 5900}]
        self.failure = None

    def request(self, url, **kwargs):
        self.requests.append((url, kwargs))
        if self.failure:
            raise self.failure
        return copy.deepcopy(self.response if kwargs.get('body') is not None else self.timing)

    @property
    def posts(self):
        return sum('body' in kwargs for _, kwargs in self.requests)


class MiniMaxMedia(Fixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.core = ProjectCore(self.a)
        _, self.vid = self.core.add_voice('真实来源', 'other', REAL, 0)
        self.config = self.dump('isolated-provider.json', {'api_key': 'PRIVATE_TEST_CREDENTIAL', 'region': 'cn',
            'base_url': 'https://api.minimax.cn', 'models': ['speech-2.8-hd'], 'default_model': 'speech-2.8-hd'})
        self.transport = StubTransport()

    def error(self, code, call):
        with self.assertRaises(MakeSoundError) as caught:
            call()
        self.assertEqual(caught.exception.code, code)
        self.assertNotIn('PRIVATE_TEST_CREDENTIAL', str(caught.exception))

    def freeze(self, **kwargs):
        return Generation(self.core, **kwargs).freeze([{'paragraph_id': 'p1', 'sentence_id': 's1', 'text': '原文。',
                        'project_voice_id': self.vid, 'pause_ms': 300}], confirmed=True, authorized=True)

    def adapter(self, snapshot, **kwargs):
        return MiniMaxProvider(self.config, authorized_job_id=snapshot['job_id'], max_calls=kwargs.pop('max_calls', 2),
                               max_characters=kwargs.pop('max_characters', 100), transport=self.transport,
                               subtitle_hosts=kwargs.pop('subtitle_hosts', ['subtitles.example.test']), environ={}, **kwargs)

    def test_inline_controls_request_subtitles_budget_and_cache(self):
        for pause in (300, 500):
            controls = [{'at': 0, 'sound': 'sighs'}, {'at': 1, 'pause_ms': pause}]
            tagged = '(sighs)原<#' + str(pause / 1000) + '#>文。'
            self.transport.timing = [{'text': tagged, 'time_begin': 100, 'time_end': 5900}]
            snap = Generation(self.core).freeze([{'paragraph_id': 'p1', 'sentence_id': 's1',
                'text': '原文。', 'project_voice_id': self.vid, 'inline_controls': controls}],
                confirmed=True, authorized=True)
            adapter = self.adapter(snap)
            result = Generation(self.core, minimax=adapter).run(snap['job_id'])
            self.assertEqual(result['status'], 'success')
            posts = [args['body'] for _, args in self.transport.requests if 'body' in args]
            self.assertEqual(posts[-1]['text'], tagged)
            self.assertNotIn('inline_controls', posts[-1]['voice_setting'])
            self.assertEqual(adapter.characters, len(tagged))
            state = read_json(self.core.managed_path(f".makesound/jobs/{snap['job_id']}/state.json"))
            self.assertEqual(state['chunks']['chunk_000000']['subtitles'],
                             [{'text': '原文。', 'start': .1, 'end': 5.9}])
        self.assertEqual(self.transport.posts, 2)

    def test_emotion_is_sent_and_separates_cached_audio(self):
        for emotion in ('angry', 'sad'):
            snap = Generation(self.core).freeze([{'paragraph_id':'p1', 'sentence_id':'s1',
                'text':'原文。', 'project_voice_id':self.vid,
                'provider_directives':{'emotion':emotion}}], confirmed=True, authorized=True)
            result = Generation(self.core, minimax=self.adapter(snap)).run(snap['job_id'])
            self.assertEqual(result['status'], 'success')
            posts = [args['body'] for _, args in self.transport.requests if 'body' in args]
            self.assertEqual(posts[-1]['voice_setting']['emotion'], emotion)
        self.assertEqual(self.transport.posts, 2)

    def test_documented_request_exact_text_omits_unverified_controls_and_key_on_download(self):
        snap = self.freeze()
        result = Generation(self.core, minimax=self.adapter(snap)).run(snap['job_id'])
        self.assertEqual(result['status'], 'success')
        post = self.transport.requests[0]
        self.assertEqual(post[0], 'https://api.minimax.cn/v1/t2a_v2')
        self.assertEqual(post[1]['body']['text'], '原文。')
        self.assertEqual(post[1]['body']['voice_setting'], {'voice_id': REAL['voice_id']})
        self.assertFalse(post[1]['body']['stream'])
        self.assertEqual(post[1]['body']['audio_setting']['format'], 'wav')
        self.assertNotIn('api_key', self.transport.requests[1][1])
        self.assertEqual(result['exports'][0]['duration_seconds'], 6.3)
        srt = self.core.managed_path(result['exports'][0]['subtitle']).read_text(encoding='utf-8')
        self.assertIn('00:00:00,100 --> 00:00:05,900', srt)
        self.assertNotIn('PRIVATE_TEST_CREDENTIAL', json.dumps(result))
        for file in self.core.directory.rglob('*.json'):
            self.assertNotIn('PRIVATE_TEST_CREDENTIAL', file.read_text(encoding='utf-8'))

    def test_default_subtitle_download_and_srt_require_no_host_flag(self):
        snap = self.freeze()
        result = Generation(self.core, minimax=self.adapter(snap, subtitle_hosts=None)).run(snap['job_id'])
        self.assertEqual(result['status'], 'success')
        body = self.transport.requests[0][1]['body']
        self.assertTrue(body['subtitle_enable'])
        self.assertEqual(body['subtitle_type'], 'sentence')
        self.assertNotIn('response_format', body)
        self.assertEqual(self.transport.posts, 1)
        self.assertNotIn('api_key', self.transport.requests[1][1])

    def test_subtitle_download_retry_is_get_only_and_reports_failure(self):
        from makesound.production import retry_subtitle_download
        snap = self.freeze()
        original = self.transport.request
        def fail_download(url, **kwargs):
            if kwargs.get('body') is None:
                raise OSError('PRIVATE_TEST_CREDENTIAL signed-url must never leak')
            return original(url, **kwargs)
        with patch.object(self.transport, 'request', side_effect=fail_download):
            result = Generation(self.core, minimax=self.adapter(snap, subtitle_hosts=None)).run(snap['job_id'])
        self.assertEqual(result['chunks']['chunk_000000']['subtitle_error'], 'subtitle_download_failed')
        self.assertNotIn('PRIVATE_TEST_CREDENTIAL', json.dumps(result))
        result = retry_subtitle_download(self.core, snap['job_id'], 'chunk_000000', transport=self.transport)
        self.assertEqual(result['status'], 'success')
        self.assertEqual(self.transport.posts, 1)
        self.assertNotIn('subtitle_error', result['chunks']['chunk_000000'])
        self.assertNotIn('subtitles.example.test', json.dumps(result))
        self.assertEqual(read_json(self.core.managed_path(f'.makesound/jobs/{snap["job_id"]}/billing-budget.json'))['attempted_calls'], 1)

    def test_legacy_receipt_without_download_source_cannot_resynthesize(self):
        from makesound.production import retry_subtitle_download
        snap = self.freeze()
        self.transport.response['data'].pop('subtitle_file')
        result = Generation(self.core, minimax=self.adapter(snap, subtitle_hosts=None)).run(snap['job_id'])
        self.assertEqual(result['chunks']['chunk_000000']['subtitle_error'], 'subtitle_url_missing')
        self.error('subtitle_source_unavailable', lambda: retry_subtitle_download(self.core, snap['job_id'], 'chunk_000000', transport=self.transport))
        self.assertEqual(self.transport.posts, 1)

    def test_subtitle_transport_blocks_private_addresses_and_credentials(self):
        with patch('socket.getaddrinfo', return_value=[(2, 1, 6, '', ('127.0.0.1', 443))]), patch('http.client.HTTPSConnection') as connection:
            self.error('unsafe_url', lambda: HTTPSMiniMaxTransport().request('https://public.example.test/subtitle'))
            connection.assert_not_called()
        self.error('unsafe_url', lambda: HTTPSMiniMaxTransport().request('http://public.example.test/subtitle'))

    def test_public_download_pins_checked_ip_uses_tls_hostname_and_no_api_key(self):
        connection = unittest.mock.MagicMock()
        connection.getresponse.return_value.status = 200
        connection.getresponse.return_value.read.return_value = b'[]'
        with patch('socket.getaddrinfo', return_value=[(2, 1, 6, '', ('8.8.8.8', 443))]), patch('http.client.HTTPSConnection', return_value=connection) as create, patch('socket.create_connection') as connect:
            HTTPSMiniMaxTransport().request('https://public.example.test/timing?signature=opaque')
            create.assert_called_once_with('public.example.test', 443, timeout=60)
            connection._create_connection(('public.example.test', 443), timeout=60)
            connect.assert_called_once_with(('8.8.8.8', 443), timeout=60)
            args = connection.request.call_args.args
            self.assertEqual(args[0], 'GET')
            self.assertNotIn('Authorization', args[3])
            self.assertIsNone(args[2])

    def test_default_constructor_never_dispatches_real_adapter(self):
        snap = self.freeze()
        with patch.object(HTTPSMiniMaxTransport, 'request', side_effect=AssertionError('No real network permitted')):
            result = Generation(self.core).run(snap['job_id'])
        self.assertEqual(result['chunks']['chunk_000000']['error'], 'provider_not_implemented')
        self.assertEqual(self.transport.posts, 0)

    def test_wrong_job_and_persistent_budget_cannot_reset_on_restart(self):
        snap = self.freeze()
        adapter = self.adapter(snap, max_calls=1, max_characters=3)
        folder = self.core.managed_path(f'.makesound/jobs/{snap["job_id"]}')
        adapter.bind(snap, folder)
        adapter.reserve('原文。')
        restarted = self.adapter(snap, max_calls=1, max_characters=3)
        restarted.bind(snap, folder)
        self.error('authorization_limit', lambda: restarted.reserve('原文。'))
        self.error('authorization_required', lambda: restarted.bind({**snap, 'job_id': 'other_job'}, folder))
        rejected = self.adapter(snap, max_calls=3)
        self.error('authorization_conflict', lambda: rejected.bind(snap, folder))
        self.error('authorization_required', lambda: rejected.synthesize(snap['chunks'][0], folder / 'unauthorized.tmp'))
        self.assertEqual(self.transport.posts, 0)

    def test_preflight_rejects_region_model_key_text_and_invalid_parameters(self):
        snap = self.freeze(); adapter = self.adapter(snap); chunk = snap['chunks'][0]
        for change, code in [({'source': {**REAL, 'region': 'international'}}, 'region_mismatch'),
                             ({'source': {**REAL, 'model': 'unconfigured-model'}}, 'model_not_configured'),
                             ({'text': 'x' * 10000}, 'text_limit'), ({'effective_settings': {'speed': 3}}, 'parameter_range')]:
            self.error(code, lambda: adapter.preflight({**chunk, **change}))
        config = read_json(self.config); config['api_key'] = 'YOUR_API_KEY_HERE'; atomic_write(self.config, config)
        self.error('invalid_credentials', lambda: adapter.preflight(chunk))
        config.update(api_key='PRIVATE_TEST_CREDENTIAL', region='international', base_url='https://api.minimax.io')
        atomic_write(self.config, config)
        self.error('provider_region_unverified', lambda: adapter.preflight({**chunk, 'source': {**REAL, 'region': 'international'}}))
        self.assertEqual(self.transport.posts, 0)

    def test_timeout_unknown_billing_blocks_retries(self):
        self.transport.failure = MakeSoundError('billing_unknown', 'Outcome unknown.')
        snap = self.freeze()
        result = Generation(self.core, minimax=self.adapter(snap)).run(snap['job_id'])
        self.assertEqual(result['chunks']['chunk_000000']['status'], 'billing_unknown')
        self.assertEqual(Generation(self.core, minimax=self.adapter(snap)).run(snap['job_id'], retry_failed=True)['status'], 'incomplete')
        self.assertEqual(self.transport.posts, 1)
        budget = read_json(self.core.managed_path(f'.makesound/jobs/{snap["job_id"]}/billing-budget.json'))
        self.assertEqual(budget['attempted_calls'], 1)

    def test_bad_success_payload_and_business_errors_never_retry(self):
        for change in [{'base_resp': {'status_code': 1000, 'status_msg': 'PRIVATE_TEST_CREDENTIAL'}},
                       {'data': {'audio': 'not-hex', 'status': 2}}, {'data': {'audio': '', 'status': 2}}]:
            with self.subTest(change=list(change)):
                self.transport.response = {'base_resp': {'status_code': 0}, 'data': {'audio': wav_bytes().hex(), 'status': 2}, **change}
                snap = self.freeze()
                result = Generation(self.core, minimax=self.adapter(snap)).run(snap['job_id'])
                self.assertEqual(result['chunks']['chunk_000000']['status'], 'billing_unknown')
                self.assertNotIn('PRIVATE_TEST_CREDENTIAL', json.dumps(result))

    def test_subtitle_host_or_invalid_timing_keeps_audio_and_never_resynthesizes(self):
        snap = self.freeze()
        result = Generation(self.core, minimax=self.adapter(snap, subtitle_hosts=[])).run(snap['job_id'])
        self.assertEqual(result['status'], 'export_incomplete')
        self.assertEqual(result['export_error'], 'subtitle_unavailable')
        self.assertEqual(result['chunks']['chunk_000000']['status'], 'success')
        self.assertEqual(len(self.transport.requests), 1)
        again = Generation(self.core, minimax=self.adapter(snap, subtitle_hosts=[])).run(snap['job_id'])
        self.assertEqual(again['status'], 'export_incomplete')
        self.assertEqual(self.transport.posts, 1)
        timing = self.dump('reviewed-timing.json', self.transport.timing)
        repair_subtitles(self.core, snap['job_id'], 'chunk_000000', timing)
        result = Generation(self.core).export_existing(snap['job_id'])
        self.assertEqual(result['status'], 'success')
        self.assertEqual(self.transport.posts, 1)
        cached_audio = self.core.managed_path(result['chunks']['chunk_000000']['path'])
        cached_audio.write_bytes(b'broken')
        repaired = Generation(self.core, minimax=self.adapter(snap, subtitle_hosts=[])).run(snap['job_id'], retry_local=True)
        self.assertEqual(repaired['status'], 'success')
        self.assertEqual(repaired['chunks']['chunk_000000']['timing_source'], 'reviewed_import')
        self.assertEqual(self.transport.posts, 1)

    def test_reject_estimated_wrong_text_overlap_nonfinite_and_out_of_bounds_timing(self):
        for rows in [[{'text': '原文。', 'time_begin': 0, 'time_end': 6001.1}],
                     [{'text': '改写。', 'time_begin': 0, 'time_end': 1000}],
                     [{'text': '原文。', 'time_begin': False, 'time_end': 1000}],
                     [{'text': '原文。', 'time_begin': 0, 'time_end': float('nan')}],
                     [{'text': '原', 'time_begin': 0, 'time_end': 2000}, {'text': '文。', 'time_begin': 1000, 'time_end': 5000}], []]:
            self.error('subtitle_unavailable', lambda: normalize_subtitles(rows, '原文。', 6))

    def test_local_conversion_failure_recovers_from_receipt_without_network(self):
        snap = self.freeze(); media = MediaTools()
        with patch.object(media, 'convert', side_effect=MakeSoundError('media_conversion_failed', 'Local failure.')):
            result = Generation(self.core, minimax=self.adapter(snap, media=media)).run(snap['job_id'])
        self.assertEqual(result['chunks']['chunk_000000']['status'], 'repair_required')
        self.assertEqual(self.transport.posts, 1)
        self.transport.failure = AssertionError('Local recovery must never request synthesis or subtitles')
        # Remove credentials: received-audio repair is entirely local.
        self.config.unlink()
        capture = io.StringIO()
        with patch('sys.stdout', capture):
            code = production_main(['repair-audio', '--project', str(self.a), '--job', snap['job_id'], '--minimax-config', str(self.config)])
        self.assertEqual(code, 0)
        result = json.loads(capture.getvalue())
        self.assertEqual(result['status'], 'success')
        self.assertEqual(self.transport.posts, 1)

    def test_damaged_success_or_cache_blocks_charge_and_local_export(self):
        snap = self.freeze(); engine = Generation(self.core, minimax=self.adapter(snap))
        result = engine.run(snap['job_id'])
        audio = self.core.managed_path(result['chunks']['chunk_000000']['path'])
        audio.write_bytes(b'broken')
        self.error('artifact_repair_required', lambda: Generation(self.core).export_existing(snap['job_id']))
        result = Generation(self.core, minimax=self.adapter(snap)).run(snap['job_id'], retry_failed=True)
        self.assertEqual(result['chunks']['chunk_000000']['status'], 'repair_required')
        self.assertEqual(self.transport.posts, 1)
        result = Generation(self.core, minimax=self.adapter(snap)).run(snap['job_id'], retry_local=True)
        self.assertEqual(result['status'], 'success')
        self.assertEqual(self.transport.posts, 1)

    def test_mp3_is_real_codec_measured_and_preview_remains_independent_wav(self):
        snap = self.freeze(output_format='mp3')
        result = Generation(self.core, minimax=self.adapter(snap)).run(snap['job_id'])
        self.assertEqual(result['status'], 'success')
        entry = result['exports'][0]
        self.assertTrue(entry['audio'].endswith('.mp3'))
        metadata = MediaTools().probe(self.core.managed_path(entry['audio']))
        self.assertEqual(metadata['codec'], 'mp3')
        self.assertLess(abs(metadata['duration_seconds'] - 6.3), .15)
        self.assertEqual(self.core.read()['project_settings']['audio_format'], 'wav')
        preview = self.core.preview_state(self.vid)
        self.assertEqual(preview['status'], 'current')
        self.assertTrue(preview['preview']['path'].endswith('.wav'))
        self.core.managed_path(entry['audio']).unlink()
        self.assertEqual(self.core.preview_state(self.vid)['status'], 'current')
        self.assertEqual(Generation(self.core).export_existing(snap['job_id'])['status'], 'success')
        self.assertEqual(self.transport.posts, 1)

    def test_fake_mp3_and_mixed_rate_export(self):
        _, fake_id = self.core.add_voice('Fake', 'other', SOURCE, self.core.read()['revision'])
        segments = [{'paragraph_id': 'p1', 'sentence_id': 's1', 'project_voice_id': self.vid, 'text': '原文。'},
                    {'paragraph_id': 'p1', 'sentence_id': 's2', 'project_voice_id': fake_id, 'text': 'Fake。'}]
        snap = Generation(self.core, output_format='mp3').freeze(segments, confirmed=True, authorized=True)
        result = Generation(self.core, minimax=self.adapter(snap)).run(snap['job_id'])
        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['exports'][0]['duration_seconds'], 12)
        self.assertEqual(MediaTools().probe(self.core.managed_path(result['exports'][0]['audio']))['codec'], 'mp3')

    def test_missing_media_tools_reject_mp3_before_any_request(self):
        media = MediaTools(ffmpeg='invalid', ffprobe='invalid')
        media.ffmpeg = None
        self.error('media_tools_missing', lambda: self.freeze(media=media, output_format='mp3'))
        self.assertEqual(self.transport.posts, 0)

        capture = io.StringIO()
        with patch('sys.stdout', capture), patch('makesound.minimax_provider.load_minimax', side_effect=AssertionError('Do not read credentials without execution authorization')):
            code = production_main(['run', '--project', str(self.a), '--job', 'job_not_authorized'])
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(capture.getvalue())['code'], 'authorization_required')

    def test_wav_synthesis_and_subtitles_without_external_tools(self):
        media = MediaTools(ffmpeg='missing-ffmpeg', ffprobe='missing-ffprobe')
        snap = self.freeze(media=media)
        with patch.object(media, '_run', side_effect=AssertionError('No external media process')):
            result = Generation(self.core, media=media, minimax=self.adapter(snap, media=media)).run(snap['job_id'])
        self.assertEqual(result['status'], 'success')
        self.assertEqual(self.transport.posts, 1)
        audio = self.core.managed_path(result['exports'][0]['audio'])
        self.assertAlmostEqual(duration(audio), 6.3)
        self.assertTrue(self.core.managed_path(result['exports'][0]['subtitle']).is_file())
        with wave.open(str(audio), 'rb') as stream:
            self.assertEqual((stream.getnchannels(), stream.getsampwidth(), stream.getframerate()), (1, 2, 32000))
        self.assertEqual(Generation(self.core, media=media).export_existing(snap['job_id'])['status'], 'success')
        self.assertEqual(self.transport.posts, 1)

    def test_wav_receipt_repair_without_external_tools_or_new_requests(self):
        snap = self.freeze()
        media = MediaTools(ffmpeg='missing-ffmpeg', ffprobe='missing-ffprobe')
        with patch.object(media, 'convert', side_effect=MakeSoundError('media_conversion_failed', 'Local failure.')):
            first = Generation(self.core, minimax=self.adapter(snap, media=media)).run(snap['job_id'])
        self.assertEqual(first['chunks']['chunk_000000']['status'], 'repair_required')
        self.config.unlink()
        self.transport.failure = AssertionError('Repair must not send a request')
        result = Generation(self.core, media=media, minimax=self.adapter(snap, media=media)).run(snap['job_id'], retry_local=True)
        self.assertEqual(result['status'], 'success')
        self.assertEqual(self.transport.posts, 1)

    def test_matching_wav_segments_merge_with_real_subtitle_offsets_without_tools(self):
        media = MediaTools(ffmpeg='missing-ffmpeg', ffprobe='missing-ffprobe')
        snap = Generation(self.core, media=media).freeze([
            {'paragraph_id': 'p1', 'sentence_id': 's1', 'text': '原文。', 'project_voice_id': self.vid, 'pause_ms': 300},
            {'paragraph_id': 'p1', 'sentence_id': 's2', 'text': '原文。', 'project_voice_id': self.vid}],
            confirmed=True, authorized=True)
        with patch.object(media, '_run', side_effect=AssertionError('No media subprocess')):
            result = Generation(self.core, media=media, minimax=self.adapter(snap, media=media)).run(snap['job_id'])
        self.assertEqual(result['status'], 'success')
        self.assertEqual(self.transport.posts, 2)
        export = result['exports'][0]
        self.assertAlmostEqual(duration(self.core.managed_path(export['audio'])), 12.3)
        subtitles = self.core.managed_path(export['subtitle']).read_text(encoding='utf-8')
        self.assertIn('00:00:00,100 --> 00:00:05,900', subtitles)
        self.assertIn('00:00:06,400 --> 00:00:12,200', subtitles)

    def test_transport_rejects_redirect_and_does_not_forward_credentials(self):
        connection = unittest.mock.MagicMock()
        connection.getresponse.return_value.status = 302
        with patch('http.client.HTTPSConnection', return_value=connection):
            self.error('billing_unknown', lambda: HTTPSMiniMaxTransport().request('https://api.minimax.cn/v1/t2a_v2', body={'text': '原文。'}, api_key='PRIVATE_TEST_CREDENTIAL'))
        self.assertEqual(connection.request.call_count, 1)
        self.transport.response['data']['subtitle_file'] = 'https://subtitles.example.test/sentence.json?key=PRIVATE_TEST_CREDENTIAL'
        snap = self.freeze()
        result = Generation(self.core, minimax=self.adapter(snap)).run(snap['job_id'])
        self.assertEqual(result['status'], 'export_incomplete')
        self.assertEqual(len(self.transport.requests), 1)

    def test_plan_freezes_task_mp3_without_network_or_project_changes(self):
        request = self.dump('structured-sentences.json', [{'paragraph_id': 'p1', 'sentence_id': 's1', 'text': '原文。', 'project_voice_id': self.vid}])
        before = self.core.path.read_bytes()
        result = plan(self.core, request_path=request, confirmed=True, audio_format='mp3')
        self.assertEqual(result['audio_format'], 'mp3')
        self.assertFalse(result['paid_execution_authorized'])
        self.assertEqual(self.core.path.read_bytes(), before)
        self.assertEqual(self.transport.posts, 0)


if __name__ == '__main__':
    unittest.main()
