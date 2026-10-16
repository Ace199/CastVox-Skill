"""Compile reviewed inline controls without changing the manuscript."""
from collections import Counter
import re

from .errors import require
from .providers import MINIMAX_DOCUMENTED_MODELS
from .storage import digest

SOUNDS = frozenset('laughs chuckle coughs clear-throat groans breath pant inhale exhale gasps sniffs sighs snorts burps lip-smacking humming hissing emm sneezes'.split())


def token(control):
    if 'sound' in control:
        return '(' + control['sound'] + ')'
    return '<#' + format(control['pause_ms'] / 1000, '.2f').rstrip('0').rstrip('.') + '#>'


def request_text(chunk):
    text = chunk['text']
    controls = chunk.get('inline_controls', [])
    require(isinstance(controls, list), 'invalid_inline_control', 'Inline controls must be a list.')
    if not controls:
        return text
    source = chunk['source']
    require(source['provider'] == 'minimax' and source['model'] in MINIMAX_DOCUMENTED_MODELS,
            'unsupported_directive', 'Inline controls require a documented MiniMax model.')
    require('<#' not in text and not any('(' + sound + ')' in text for sound in SOUNDS),
            'invalid_inline_control', 'Keep control tags out of the manuscript; use inline_controls.')
    previous, last_pause, pieces = -1, None, []
    cursor = 0
    for control in controls:
        require(isinstance(control, dict) and set(control) in ({'at', 'sound'}, {'at', 'pause_ms'}),
                'invalid_inline_control', 'Each control needs at and exactly one of sound or pause_ms.')
        at = control['at']
        require(type(at) is int and previous < at <= len(text), 'invalid_inline_control',
                'Offsets must be unique, increasing Unicode character positions within the manuscript.')
        if 'sound' in control:
            require(isinstance(control['sound'], str) and control['sound'] in SOUNDS
                    and source['model'] in {'speech-2.8-hd', 'speech-2.8-turbo'},
                    'unsupported_directive', 'This sound tag requires speech-2.8-hd or speech-2.8-turbo.')
        else:
            ms = control['pause_ms']
            require(type(ms) is int and 10 <= ms <= 99990 and ms % 10 == 0,
                    'invalid_inline_control', 'Inline pause must be 10–99990 ms in steps of 10 ms.')
            require(any(c.isalnum() for c in text[:at]) and any(c.isalnum() for c in text[at:])
                    and (last_pause is None or any(c.isalnum() for c in text[last_pause:at])),
                    'invalid_inline_control', 'Pauses must separate spoken text and cannot be consecutive.')
            last_pause = at
        pieces.extend((text[cursor:at], token(control)))
        cursor = previous = at
    return ''.join(pieces) + text[cursor:]


def subtitle_cleaner(controls):
    remaining = Counter(token(control) for control in (controls or []))
    pattern = re.compile('|'.join(re.escape(t) for t in remaining)) if remaining else None
    def clean(text):
        def replace(match):
            value = match.group()
            if remaining[value]:
                remaining[value] -= 1
                return ''
            return value
        return pattern.sub(replace, text) if pattern else text
    return clean


def request_identity(chunk):
    return digest({**{key: chunk[key] for key in ('source', 'text', 'effective_settings', 'pause_ms')},
                   **{key: chunk[key] for key in ('provider_directives', 'inline_controls') if chunk.get(key)}})
