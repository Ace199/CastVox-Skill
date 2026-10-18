import tempfile
import os
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

from makesound.errors import MakeSoundError
from makesound.media import MediaTools


class WavFallback(unittest.TestCase):
    def setUp(self):
        parent = Path(__file__).resolve().parents[2] / '.test-tmp'
        parent.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=parent)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'source.wav'
        self.target = self.root / 'target.wav'
        with wave.open(str(self.source), 'wb') as stream:
            stream.setnchannels(1); stream.setsampwidth(2); stream.setframerate(32000)
            stream.writeframes(b'\x01\x00' * 3200)
        self.media = MediaTools(ffmpeg='absent', ffprobe='absent')

    def test_verified_pcm_samples_are_preserved_without_subprocess(self):
        with patch.object(self.media, '_run', side_effect=AssertionError('No subprocess')):
            metadata = self.media.convert(self.source, self.target, format='wav')
            self.assertEqual(self.media.probe(self.target), metadata)
        self.assertEqual(metadata['codec'], 'pcm_s16le')
        self.assertAlmostEqual(metadata['duration_seconds'], .1)
        self.assertEqual(self.target.read_bytes(), self.source.read_bytes())

    def test_truncated_or_mislabeled_pcm_is_not_delivered(self):
        for data in [self.source.read_bytes()[:-2], b'#EXTM3U\nhttps://example.test/audio']:
            with self.subTest(size=len(data)):
                self.source.write_bytes(data)
                with self.assertRaises(MakeSoundError) as caught:
                    self.media.convert(self.source, self.target, format='wav')
                self.assertEqual(caught.exception.code, 'invalid_audio')
                self.assertFalse(self.target.exists())

    def test_no_tools_cannot_encode_mp3_or_resample(self):
        for format, rate in [('mp3', 32000), ('wav', 16000)]:
            with self.subTest(format=format, rate=rate):
                with self.assertRaises(MakeSoundError) as caught:
                    self.media.convert(self.source, self.target, format=format, rate=rate)
                self.assertEqual(caught.exception.code, 'media_tools_missing')
                self.assertFalse(self.target.exists())

    @unittest.skipUnless(os.name == 'nt', 'Windows WinGet lookup')
    def test_existing_winget_pair_is_found_when_path_is_restricted(self):
        package = self.root / 'AppData/Local/Microsoft/WinGet/Packages/Gyan.FFmpeg_test/ffmpeg-8.1.2-full_build/bin'
        package.mkdir(parents=True)
        for name in ['ffmpeg.exe', 'ffprobe.exe']:
            (package / name).write_bytes(b'local-existing-tool')
        with patch('makesound.media.shutil.which', return_value=None), patch('makesound.media.Path.home', return_value=self.root):
            media = MediaTools()
        self.assertEqual(Path(media.ffmpeg), package / 'ffmpeg.exe')
        self.assertEqual(Path(media.ffprobe), package / 'ffprobe.exe')
