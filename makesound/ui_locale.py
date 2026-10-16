"""CastVox language handoff; the agent supplies its response language at launch."""
import os
import re

from .errors import require


def normalize_ui_language(value):
    """Map supported language tags to the two shipped UI translations."""
    if not isinstance(value, str):
        return None
    tag = value.strip().replace('_', '-').lower()
    if not re.fullmatch(r'(zh|en)(?:-[a-z0-9]{1,8})*', tag):
        return None
    return 'zh-CN' if tag.split('-')[0] == 'zh' else 'en'


def resolve_ui_language(explicit=None):
    """Explicit override wins over the caller's CASTVOX_UI_LANGUAGE handoff.

    CASTVOX_UI_LANGUAGE is our own integration contract, not a host-defined
    variable. Unknown/missing host input lets Studio use its Chinese default.
    """
    if explicit is not None:
        language = normalize_ui_language(explicit)
        require(language is not None, 'invalid_ui_language', 'UI language must be Chinese (zh-CN) or English (en).')
        return language
    return normalize_ui_language(os.environ.get('CASTVOX_UI_LANGUAGE'))
