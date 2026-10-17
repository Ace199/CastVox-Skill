"""Safe local entry choices. Local completeness never proves authentication."""
from urllib.parse import urlsplit

from .config_loader import load_minimax
from .provider_config import read_models
from .storage import read_json


def _key_ready(value):
    if not isinstance(value, str) or not value or value != value.strip() or any(c.isspace() for c in value):
        return False
    lowered = value.lower()
    return lowered not in {'placeholder', 'test', 'fake', 'changeme', 'replace_me'} and not any(
        marker in lowered for marker in ('your_', 'your-', 'placeholder', '<', '>'))


def _state(provider, path, environ):
    models = read_models(path)
    result = {'provider': provider, 'configured': False, 'status': 'config_required',
              'authentication': 'not_verified', 'network_calls': 0,
              'models': models['models'], 'selected_model': None, 'model_choice_required': False}
    if models['model_status'] != 'configured':
        return result
    try:
        if provider == 'minimax':
            config = load_minimax(path, environ=environ)
            summary = config.summary()
            ready = _key_ready(config.api_key) and summary['api_key_present']
        else:
            # Future adapter opt-in: static shape/origin checks only; never probe.
            obj = read_json(path)
            origin = urlsplit(obj.get('base_url', ''))
            ready = (obj.get('auth_mode') == 'api_key' and _key_ready(obj.get('api_key'))
                     and obj.get('region') == 'cn' and origin.scheme == 'https'
                     and origin.hostname == 'openspeech.bytedance.com' and origin.port in (None, 443)
                     and not origin.username and not origin.password and not origin.query
                     and not origin.fragment and origin.path in ('', '/')
                     and isinstance(obj.get('resource_id'), str) and bool(obj['resource_id'].strip())
                     and isinstance(obj.get('tts_endpoint'), str) and obj['tts_endpoint'].startswith('/api/'))
        if ready:
            result.update(configured=True, status='locally_configured', verification='static_only')
            result['selected_model'] = models['default_model'] or (models['models'][0]['id'] if len(models['models']) == 1 else None)
            result['model_choice_required'] = result['selected_model'] is None
    except Exception:
        # Neither exception messages nor credential-bearing objects cross this boundary.
        pass
    return result


def choices(config_dir=None, *, environ=None, supported_providers=('minimax',)):
    """Offer manual binding first, then recommendations from adapted providers.

    Exactly one locally configured supported provider becomes the default. More
    than one requires an explicit choice. The supported_providers argument is an
    adapter capability declaration, not an authentication claim.
    """
    from studio_config_editor import config_path
    supported = tuple(supported_providers)
    if not supported or len(set(supported)) != len(supported) or any(p not in ('minimax', 'volcengine') for p in supported):
        raise ValueError('Unsupported provider capability declaration')
    states = [_state(p, config_path(p, config_dir), environ) for p in ('minimax', 'volcengine') if p in supported]
    configured = [state['provider'] for state in states if state['configured']]
    names = {'minimax': 'MiniMax', 'volcengine': '火山引擎'}
    offered = configured if configured else [state['provider'] for state in states]
    providers = [{'id': f'2.{chr(97 + index)}', 'provider': provider,
                  'label': names[provider] if provider in configured else f'配置 {names[provider]}',
                  'action': 'recommend' if provider in configured else 'configure',
                  'configured': provider in configured} for index, provider in enumerate(offered)]
    return {'options': [{'id': '1', 'label': '自己配置声音', 'action': 'manual'},
                        {'id': '2', 'label': '推荐音色', 'action': 'recommend', 'providers': providers}],
            'default_provider': configured[0] if len(configured) == 1 else None,
            'config_required': not bool(configured), 'provider_choice_required': len(configured) > 1,
            'providers': states, 'authentication': 'not_verified', 'network_calls': 0}


def configure(provider, config_dir=None, opener=None):
    """Explicit MiniMax setup only; existing credentials are never overwritten."""
    if provider != 'minimax':
        raise ValueError('当前仅支持 MiniMax 配置与推荐入口')
    from studio_config_editor import config_path, open_config
    result = open_config(provider, config_dir=config_dir, opener=opener)
    return {**result, 'provider': provider, 'config_path': str(config_path(provider, config_dir)),
            'authentication': 'not_verified', 'network_calls': 0}
