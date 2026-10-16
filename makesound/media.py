"""Local-only audio conversion. No shell, remote protocols, or vendor requests."""
import json
import os
import shutil
import subprocess
import wave
from pathlib import Path

from .errors import MakeSoundError, require
from .storage import reject_links


class MediaTools:
    def __init__(self, ffmpeg=None, ffprobe=None):
        self.ffmpeg = ffmpeg or shutil.which('ffmpeg')
        self.ffprobe = ffprobe or shutil.which('ffprobe')
        # Some managed hosts deliberately omit the user's PATH. Reuse the
        # existing per-user WinGet package without installing or changing PATH.
        if os.name == 'nt' and not ffmpeg and not ffprobe and not self.available:
            packages = Path.home() / 'AppData/Local/Microsoft/WinGet/Packages'
            try:
                for binary_dir in sorted(packages.glob('Gyan.FFmpeg_*/ffmpeg*/bin'), reverse=True):
                    pair = binary_dir / 'ffmpeg.exe', binary_dir / 'ffprobe.exe'
                    if all(path.is_file() for path in pair):
                        self.ffmpeg, self.ffprobe = map(str, pair)
                        break
            except OSError:
                pass  # A restricted install directory must not block PCM WAV.

    @property
    def available(self):
        return bool(self.ffmpeg and self.ffprobe and Path(self.ffmpeg).is_file() and Path(self.ffprobe).is_file())

    def require_available(self):
        require(self.available,
                'media_tools_missing', 'FFmpeg and FFprobe are required for this output.')

    def _run(self, command):
        try:
            result = subprocess.run(command, capture_output=True, timeout=120,
                                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            require(result.returncode == 0, 'media_conversion_failed', 'Local audio processing failed; source audio is retained.')
            return result.stdout
        except (OSError, subprocess.TimeoutExpired):
            raise MakeSoundError('media_conversion_failed', 'Local audio processing could not finish; source audio is retained.') from None

    def convert(self, source, target, *, format, rate=32000):
        require(format in {'wav', 'mp3'}, 'export_not_implemented', 'Only WAV and MP3 conversion is implemented.')
        reject_links(Path(source)); reject_links(Path(target))
        source, target = Path(source).resolve(), Path(target).resolve()
        require(source.is_file() and source != target, 'invalid_audio', 'Expected an existing local source file.')
        if not self.available and format == 'wav':
            metadata = self._pcm_probe(source)
            require(metadata['sample_rate'] == rate, 'media_tools_missing',
                    'Resampling requires external media tools; original WAV is retained.')
            shutil.copyfile(source, target)
            return metadata
        self.require_available()
        codec = ['-c:a', 'pcm_s16le'] if format == 'wav' else ['-c:a', 'libmp3lame', '-b:a', '128k']
        self._run([self.ffmpeg, '-nostdin', '-hide_banner', '-loglevel', 'error', '-y',
                   '-protocol_whitelist', 'file,pipe', '-f', 'wav', '-i', str(source), '-map', '0:a:0', '-vn',
                   '-map_metadata', '-1', '-ac', '1', '-ar', str(rate), *codec, '-f', format, str(target)])
        return self.probe(target)

    def probe(self, path):
        reject_links(Path(path))
        if not self.available:
            return self._pcm_probe(path)
        self.require_available()
        try:
            obj = json.loads(self._run([self.ffprobe, '-v', 'error', '-protocol_whitelist', 'file,pipe',
                                       '-select_streams', 'a:0', '-show_entries',
                                       'stream=codec_name,sample_rate,channels:format=duration', '-of', 'json', str(Path(path).resolve())]))
            stream = obj['streams'][0]
            seconds = float(obj['format']['duration'])
            require(0 < seconds < 86400, 'invalid_audio', 'Audio duration is invalid.')
            return {'duration_seconds': seconds, 'codec': stream['codec_name'],
                    'sample_rate': int(stream['sample_rate']), 'channels': stream['channels']}
        except (ValueError, KeyError, IndexError, TypeError):
            raise MakeSoundError('invalid_audio', 'Local audio metadata could not be verified.') from None

    @staticmethod
    def _pcm_probe(path):
        """Validate actual PCM frames, not the filename or declared duration."""
        try:
            with wave.open(str(path), 'rb') as audio:
                channels, width, rate, frames = (audio.getnchannels(), audio.getsampwidth(),
                                                  audio.getframerate(), audio.getnframes())
                require(audio.getcomptype() == 'NONE' and channels == 1 and width == 2,
                        'invalid_audio', 'Fallback requires mono 16-bit PCM WAV.')
                require(rate > 0 and 0 < frames / rate < 86400, 'invalid_audio', 'Audio duration is invalid.')
                remaining = frames
                while remaining:
                    count = min(remaining, 32768)
                    require(len(audio.readframes(count)) == count * channels * width,
                            'invalid_audio', 'PCM WAV payload is truncated.')
                    remaining -= count
            return {'duration_seconds': frames / rate, 'codec': 'pcm_s16le',
                    'sample_rate': rate, 'channels': channels}
        except (OSError, EOFError, wave.Error, ValueError):
            raise MakeSoundError('invalid_audio', 'Local PCM WAV could not be verified.') from None


def main():
    """Offline discovery only: no provider configuration, network or installs."""
    media = MediaTools()
    print(json.dumps({'status': 'ready' if media.available else 'wav_only',
                      'ffmpeg': media.ffmpeg, 'ffprobe': media.ffprobe,
                      'pcm_wav': True, 'mp3_and_resampling': media.available,
                      'network_calls': 0, 'downloads': 0}))


if __name__ == '__main__':
    main()
