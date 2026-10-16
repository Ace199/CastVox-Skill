import unittest
from makesound.errors import MakeSoundError


class InlineControls(unittest.TestCase):
    def test_compilation_preserves_source_and_validates_offsets(self):
        from makesound.inline_controls import request_text
        source = {'provider': 'minimax', 'model': 'speech-2.8-hd'}
        chunk = {'source': source, 'text': '甲，乙。', 'inline_controls': [
            {'at': 0, 'sound': 'sighs'}, {'at': 2, 'pause_ms': 300}]}
        self.assertEqual(request_text(chunk), '(sighs)甲，<#0.3#>乙。')
        self.assertEqual(chunk['text'], '甲，乙。')
        for controls in ([{'at': 0, 'pause_ms': 300}], [{'at': 4, 'pause_ms': 300}],
                         [{'at': 2, 'pause_ms': 301}], [{'at': 2, 'pause_ms': 0}],
                         [{'at': 2, 'pause_ms': 100000}], [{'at': True, 'sound': 'sighs'}],
                         [{'at': 2, 'sound': 'invented'}],
                         [{'at': 2, 'pause_ms': 100}, {'at': 2, 'pause_ms': 200}]):
            with self.subTest(controls=controls), self.assertRaises(MakeSoundError):
                request_text({**chunk, 'inline_controls': controls})
        with self.assertRaises(MakeSoundError):
            request_text({**chunk, 'source': {**source, 'model': 'speech-2.6-hd'}})

    def test_only_confirmed_tokens_are_removed_from_subtitles(self):
        from makesound.minimax_provider import normalize_subtitles
        controls = [{'at': 0, 'sound': 'sighs'}, {'at': 2, 'pause_ms': 300}]
        rows = [{'text': '(sighs)', 'time_begin': 0, 'time_end': 300},
                {'text': '甲，<#0.3#>乙。', 'time_begin': 300, 'time_end': 2000}]
        clean = normalize_subtitles(rows, '甲，乙。', 2, inline_controls=controls)
        self.assertEqual(clean, [{'text': '甲，乙。', 'start': .3, 'end': 2}])
        for text in ('(laughs)甲，乙。', '(sighs)(sighs)甲，乙。', '甲，丙。'):
            with self.assertRaises(MakeSoundError):
                normalize_subtitles([{'text': text, 'time_begin': 0, 'time_end': 2000}],
                                    '甲，乙。', 2, inline_controls=controls)
