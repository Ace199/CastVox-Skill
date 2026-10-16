from .providers import performance_directives
"""Opt-in MiniMax non-streaming transport with durable received-audio receipts.

Official contract checked 2026-10-16. Unit tests inject transport; no live calls
are made by configuration, Studio, or the default Generation constructor.
"""
import hashlib
import http.client
import io
import ipaddress
import socket
import json
import math
import os
import re
import wave
from pathlib import Path
from urllib.parse import urlsplit, unquote

from .inline_controls import request_text, request_identity, subtitle_cleaner
from .config_loader import load_minimax
from .errors import MakeSoundError, require
from .media import MediaTools
from .provider_config import read_models
from .providers import duration, effective, MINIMAX_DOCUMENTED_MODELS
from .storage import _pairs, atomic_write, read_json, digest, file_lock, reject_links


DOCUMENTED_MODELS = MINIMAX_DOCUMENTED_MODELS


def decode_json(payload):
    return json.loads(payload.decode('utf-8'), object_pairs_hook=_pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))


def subtitle_source(url, *, credential=None, hosts=None):
    require(isinstance(url, str) and 0 < len(url) <= 8192, 'subtitle_url_missing', 'Subtitle download source is unavailable.')
    require(not credential or credential not in unquote(url), 'unsafe_url', 'Subtitle source contains a credential.')
    try:
        parsed = urlsplit(url)
        valid = (parsed.scheme == 'https' and parsed.hostname and parsed.port in {None, 443}
                 and parsed.username is None and parsed.password is None and not parsed.fragment
                 and not any(ord(c) < 33 or ord(c) == 127 for c in url)
                 and re.fullmatch(r'[a-zA-Z0-9.-]+', parsed.hostname)
                 and '.' in parsed.hostname and not re.fullmatch(r'[0-9.]+', parsed.hostname)
                 and not parsed.hostname.endswith('.localhost'))
        require(valid, 'unsafe_url', 'Invalid HTTPS subtitle source.')
        require(hosts is None or parsed.hostname in hosts, 'subtitle_host_blocked', 'Subtitle host is excluded by the explicit allowlist.')
    except ValueError:
        raise MakeSoundError('unsafe_url', 'Invalid HTTPS subtitle source.') from None
    return url


def download_subtitles(url, text, speech_seconds, *, transport, hosts=None, inline_controls=None):
    subtitle_source(url, hosts=hosts)
    try:
        document = transport.request(url, maximum=4 * 1024 * 1024)
    except Exception:
        raise MakeSoundError('subtitle_download_failed', 'Subtitle download failed; retry download without synthesis.') from None
    try:
        return normalize_subtitles(document, text, speech_seconds, inline_controls=inline_controls)
    except Exception:
        raise MakeSoundError('subtitle_timing_invalid', 'Subtitle timing or text failed validation.') from None


class HTTPSMiniMaxTransport:
    """One request per call; no redirects, proxy inheritance, or automatic retry."""
    def request(self, url, *, body=None, api_key=None, maximum=64 * 1024 * 1024):
        parsed = urlsplit(url)
        require(parsed.scheme == 'https' and parsed.hostname and parsed.port in {None, 443}
                and parsed.username is None and parsed.password is None and not parsed.fragment,
                'unsafe_url', 'Expected an authorized HTTPS URL.')
        pinned = None
        if body is None:
            require(api_key is None, 'unsafe_url', 'Download requests cannot carry an API Key.')
            subtitle_source(url)
            try:
                addresses = socket.getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM)
                require(bool(addresses) and all(ipaddress.ip_address(row[4][0]).is_global for row in addresses),
                        'unsafe_url', 'Subtitle downloads require public network addresses.')
                pinned = addresses[0][4][0]
            except OSError:
                raise MakeSoundError('subtitle_download_failed', 'Subtitle host could not be resolved.') from None
        connection = http.client.HTTPSConnection(parsed.hostname, 443, timeout=60)
        if pinned:
            # Pin the checked IP while retaining the original TLS hostname/SNI.
            connection._create_connection = lambda address, *args, **kwargs: socket.create_connection((pinned, address[1]), *args, **kwargs)
        headers = {'Accept': 'application/json'}
        if api_key:
            headers['Authorization'] = 'Bearer ' + api_key
        payload = None
        if body is not None:
            headers['Content-Type'] = 'application/json'
            payload = json.dumps(body, ensure_ascii=False, allow_nan=False).encode('utf-8')
        try:
            connection.request('POST' if body is not None else 'GET', parsed.path + ('?' + parsed.query if parsed.query else ''), payload, headers)
            response = connection.getresponse()
            # Deliberately do not follow Location or copy server error text.
            require(response.status == 200, 'billing_unknown', 'Provider response requires reconciliation; no automatic retry.')
            content = response.read(maximum + 1)
            require(len(content) <= maximum, 'billing_unknown', 'Provider response exceeded the local limit; reconcile before retry.')
            return decode_json(content)
        except MakeSoundError:
            raise
        except Exception:
            raise MakeSoundError('billing_unknown', 'Provider outcome is unknown; reconcile before any repeat request.') from None
        finally:
            connection.close()


def normalize_subtitles(document, text, speech_seconds, *, inline_controls=None):
    """Accept only explicit millisecond timing; never estimate from text length."""
    require(isinstance(document, list) and bool(document), 'subtitle_unavailable', 'Expected sentence timing records.')
    rows, previous = [], 0.0
    clean = subtitle_cleaner(inline_controls)
    for item in document:
        require(isinstance(item, dict) and isinstance(item.get('text'), str), 'subtitle_unavailable', 'Invalid sentence timing record.')
        start, end = item.get('time_begin'), item.get('time_end')
        require(type(start) in {int, float} and type(end) in {int, float} and math.isfinite(start) and math.isfinite(end),
                'subtitle_unavailable', 'Subtitle timestamps must be finite milliseconds.')
        start, end = start / 1000, end / 1000
        require(previous <= start < end <= speech_seconds + .001, 'subtitle_unavailable', 'Subtitle timing exceeds measured audio or overlaps.')
        visible = clean(item['text'])
        if visible.strip():
            rows.append({'start': start, 'end': end, 'text': visible})
        previous = end
    compact = lambda value: re.sub(r'\s+', '', value)
    require(compact(''.join(row['text'] for row in rows)) == compact(text), 'subtitle_unavailable',
            'Subtitle text differs from the confirmed manuscript; manual review is required.')
    return rows


class MiniMaxProvider:
    def __init__(self, config_path, *, authorized_job_id, max_characters, max_calls, transport=None, media=None, subtitle_hosts=None, environ=None):
        require(isinstance(authorized_job_id, str) and authorized_job_id, 'authorization_required', 'A specific authorized Job is required.')
        require(type(max_characters) is int and max_characters > 0 and type(max_calls) is int and max_calls > 0,
                'authorization_required', 'Explicit request and character limits are required.')
        self.config_path = Path(config_path)
        self.authorized_job_id = authorized_job_id
        self.max_characters, self.max_calls = max_characters, max_calls
        self.calls = self.characters = 0
        self.transport = transport or HTTPSMiniMaxTransport()
        self.media = media or MediaTools()
        self.subtitle_hosts = None if subtitle_hosts is None else frozenset(subtitle_hosts)
        require(all(isinstance(host, str) and re.fullmatch(r'[a-z0-9.-]+', host) and '.' in host
                    and not re.fullmatch(r'[0-9.]+', host) and not host.endswith('.localhost') for host in (self.subtitle_hosts or ())),
                'unsafe_url', 'Subtitle hosts must be explicitly trusted DNS hostnames.')
        self.environ = environ
        self.budget_path = None

    def bind(self, snapshot, folder):
        self.budget_path = None
        require(snapshot['job_id'] == self.authorized_job_id, 'authorization_required', 'Adapter authorization belongs to another Job.')
        budget_path = Path(folder) / 'billing-budget.json'
        expected = {'job_id': snapshot['job_id'], 'snapshot_hash': snapshot['snapshot_hash'],
                    'max_calls': self.max_calls, 'max_characters': self.max_characters}
        with file_lock(budget_path.with_suffix('.lock')):
            if budget_path.exists():
                saved = read_json(budget_path)
                require(all(saved.get(k) == val for k, val in expected.items()), 'authorization_conflict', 'Frozen Job budget differs; review before extending authorization.')
            else:
                atomic_write(budget_path, {**expected, 'attempted_calls': 0, 'attempted_characters': 0})
        self.budget_path = budget_path

    def reserve(self, text):
        require(self.budget_path is not None, 'authorization_required', 'Bind this adapter to the authorized frozen Job first.')
        with file_lock(self.budget_path.with_suffix('.lock')):
            budget = read_json(self.budget_path)
            require(budget['attempted_calls'] < self.max_calls and budget['attempted_characters'] + len(text) <= self.max_characters,
                    'authorization_limit', 'Authorized Job request or character limit would be exceeded.')
            budget['attempted_calls'] += 1
            budget['attempted_characters'] += len(text)
            # Reserve BEFORE dispatch. A crash cannot reset the request budget.
            atomic_write(self.budget_path, budget)

    def preflight(self, chunk):
        config = load_minimax(self.config_path, self.environ)
        require(config.api_key.lower() not in {'your_api_key_here', 'write your own keys', 'placeholder', 'test', 'fake'},
                'invalid_credentials', 'Placeholder credentials cannot authorize synthesis.')
        source = chunk['source']
        require(source['provider'] == 'minimax' and source['region'] == config.region, 'region_mismatch', 'Frozen source differs from configured region.')
        require(config.region == 'cn', 'provider_region_unverified', 'This adapter contract has only been checked for the CN endpoint.')
        models = read_models(self.config_path)
        require(models['model_status'] == 'configured' and source['model'] in {m['id'] for m in models['models']}
                and source['model'] in DOCUMENTED_MODELS, 'model_not_configured', 'Choose a configured model with a supported request contract.')
        require(isinstance(chunk['text'], str) and 0 < len(request_text(chunk)) < 10000,
                'text_limit', 'Synchronous MiniMax text must contain fewer than 10000 characters.')
        effective(source, chunk['effective_settings'])
        performance_directives(source, chunk.get('provider_directives'))
        # The provider returns mono 16-bit / 32 kHz PCM WAV. Matching WAV can
        # be validated and delivered locally even without FFmpeg/FFprobe.
        return config

    @staticmethod
    def receipt_paths(path):
        path = Path(path)
        return path.with_name(path.name + '.received.wav'), path.with_name(path.name + '.received.json')

    def synthesize(self, chunk, path, *, recovery_only=False):
        require(self.budget_path is not None, 'authorization_required', 'Bind this adapter to the authorized frozen Job first.')
        raw, receipt_path = self.receipt_paths(path)
        reject_links(raw); reject_links(receipt_path)
        request_hash = request_identity(chunk)
        if raw.exists() or receipt_path.exists():
            require(raw.is_file() and receipt_path.is_file(), 'artifact_repair_required', 'Received audio receipt is incomplete; no repeat synthesis was sent.')
            receipt = read_json(receipt_path)
            require(receipt.get('request_hash') == request_hash, 'artifact_repair_required', 'Received audio belongs to another request.')
            require(hashlib.sha256(raw.read_bytes()).hexdigest() == receipt['audio_hash'], 'artifact_repair_required', 'Received audio integrity failed; restore the original file.')
        else:
            require(not recovery_only, 'artifact_repair_required', 'No received audio is available for local repair.')
            config = self.preflight(chunk)
            self.reserve(request_text(chunk))
            self.calls += 1
            self.characters += len(request_text(chunk))
            body = {'model': chunk['source']['model'], 'text': request_text(chunk), 'stream': False,
                    'voice_setting': {'voice_id': chunk['source']['voice_id'], **effective(chunk['source'], chunk['effective_settings']), **performance_directives(chunk['source'], chunk.get('provider_directives'))},
                    'audio_setting': {'format': 'wav', 'sample_rate': 32000, 'channel': 1},
                    'subtitle_enable': True, 'subtitle_type': 'sentence', 'output_format': 'hex'}
            response = self.transport.request(config.base_url + '/v1/t2a_v2', body=body, api_key=config.api_key)
            try:
                require(type(response['base_resp']['status_code']) is int and response['base_resp']['status_code'] == 0,
                        'billing_unknown', 'Provider rejected the request; reconcile before retry.')
                require(response['data']['status'] == 2, 'billing_unknown', 'Provider did not report complete synthesis.')
                audio = bytes.fromhex(response['data']['audio'])
                require(0 < len(audio) <= 32 * 1024 * 1024, 'billing_unknown', 'Provider audio is empty or too large.')
                with wave.open(io.BytesIO(audio), 'rb') as received:
                    require((received.getnchannels(), received.getsampwidth(), received.getframerate(), received.getcomptype())
                            == (1, 2, 32000, 'NONE'), 'billing_unknown', 'Provider encoding differs from the requested PCM contract.')
                    count = received.getnframes()
                    require(count > 0 and len(received.readframes(count)) == count * 2,
                            'billing_unknown', 'Provider PCM payload is truncated.')
                # Persist audio before attempting subtitle retrieval or conversion.
                incoming = raw.with_suffix('.incoming')
                reject_links(incoming)
                try:
                    with incoming.open('wb') as stream:
                        stream.write(audio); stream.flush(); os.fsync(stream.fileno())
                    os.replace(incoming, raw)
                finally:
                    incoming.unlink(missing_ok=True)
                receipt = {'audio_hash': hashlib.sha256(audio).hexdigest(), 'request_hash': request_hash,
                           'subtitles': None, 'subtitle_status': 'unavailable'}
                atomic_write(receipt_path, receipt)
                try:
                    url = subtitle_source(response['data'].get('subtitle_file'), credential=config.api_key)
                    # Private recovery receipt only; never included in state/API results.
                    receipt['subtitle_download_url'] = url
                    atomic_write(receipt_path, receipt)
                    receipt['subtitles'] = download_subtitles(url, chunk['text'], duration(raw), inline_controls=chunk.get('inline_controls'),
                                                             transport=self.transport, hosts=self.subtitle_hosts)
                    receipt['subtitle_status'] = 'verified_timing'
                    receipt.pop('subtitle_error', None)
                except Exception as exc:
                    receipt['subtitle_error'] = (exc.code if isinstance(exc, MakeSoundError) and exc.code in {
                        'subtitle_url_missing', 'unsafe_url', 'subtitle_host_blocked',
                        'subtitle_download_failed', 'subtitle_timing_invalid'} else 'subtitle_download_failed')
                atomic_write(receipt_path, receipt)
            except MakeSoundError:
                raise
            except Exception:
                raise MakeSoundError('billing_unknown', 'Provider result could not be durably validated; do not repeat synthesis.') from None
        try:
            # Force actual PCM WAV input before invoking a decoder; never let a
            # mislabeled response be interpreted as a playlist or external file.
            require(duration(raw) > 0, 'invalid_audio', 'Received audio is not measurable PCM WAV.')
            self.media.convert(raw, path, format='wav', rate=32000)
            speech_seconds = duration(path)
            with wave.open(str(path), 'rb') as stream:
                frames = stream.readframes(stream.getnframes())
            with wave.open(str(path), 'wb') as stream:
                stream.setnchannels(1); stream.setsampwidth(2); stream.setframerate(32000)
                stream.writeframes(frames + b'\x00\x00' * round(chunk['pause_ms'] * 32))
            return {'duration_seconds': duration(path), 'speech_seconds': speech_seconds,
                    'subtitles': receipt['subtitles'], 'subtitle_status': receipt['subtitle_status'],
                    'timing_source': receipt.get('timing_source', 'provider'),
                    **({'subtitle_error': receipt['subtitle_error']} if receipt.get('subtitle_error') else {})}
        except Exception:
            raise MakeSoundError('artifact_repair_required', 'Received audio was retained; retry local processing without another synthesis.') from None
