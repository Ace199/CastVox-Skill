"""Read-only, allowlisted provider model metadata. No network transport."""

def safe_text(value, maximum=128):
    import re
    return (isinstance(value, str) and 0 < len(value) <= maximum and value == value.strip()
            and not any(ord(c) < 32 for c in value)
            and not re.search(r'(?i)bearer\s+\S+|\bsk-[a-z0-9_-]{12,}', value))

def read_models(path):
    """Read only two allowlisted fields; never return exception or credential text."""
    if path is None or not path.exists():
        return dict(models=[], default_model=None, model_status='not_configured', message='尚未配置模型')
    try:
        from makesound.storage import read_json
        obj = read_json(path)
        if not isinstance(obj, dict):
            raise ValueError()
        from makesound.validation import SENSITIVE
        secrets = []
        def collect(value, sensitive=False):
            if isinstance(value, dict):
                for key, child in value.items():
                    collect(child, sensitive or bool(SENSITIVE.search(key)))
            elif isinstance(value, list):
                for child in value:
                    collect(child, sensitive)
            elif sensitive and isinstance(value, str) and value:
                secrets.append(value)
        collect(obj)
        raw = obj.get('models')
        if raw is None or raw == []:
            return dict(models=[], default_model=None, model_status='not_configured', message='尚未配置模型；这不表示 API Key 无效')
        if not isinstance(raw, list) or len(raw) > 100:
            raise ValueError()
        models = []
        for item in raw:
            identity = item if isinstance(item, str) else item.get('id') if isinstance(item, dict) else None
            label = identity if isinstance(item, str) else item.get('name', identity) if isinstance(item, dict) else None
            if not safe_text(identity) or not safe_text(label, 160) or any(m['id'] == identity for m in models):
                raise ValueError()
            if any(secret in identity or secret in label for secret in secrets):
                raise ValueError()
            models.append(dict(id=identity, name=label))
        default = obj.get('default_model')
        if default is not None and (not safe_text(default) or default not in [m['id'] for m in models]):
            return dict(models=models, default_model=None, model_status='invalid_default', message='default_model 不在 models 中，请在本机配置中核对；不会修改文件')
        return dict(models=models, default_model=default, model_status='configured', message='已读取模型配置；未进行鉴权或模型兼容性验证')
    except Exception:
        return dict(models=[], default_model=None, model_status='invalid_model_config', message='无法读取有效模型配置；未进行鉴权，不代表 API Key 无效')

