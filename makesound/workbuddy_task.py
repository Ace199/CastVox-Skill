"""Resume the host's pending managed TaskOutput rather than engine runDefault.

The host agent must keep waiting on its background task after opening Studio.
The command returns the saved Answer only after HTTP completion finishes.
"""
import os
import re

from .errors import require


def environment_target():
    if not os.environ.get('WORKBUDDY_CONFIG_DIR'):
        return None
    session = os.environ.get('CODEBUDDY_SESSION_ID', '')
    require(re.fullmatch(r'[A-Za-z0-9_-]{1,128}', session), 'harness_unavailable',
            'Run Studio from the originating WorkBuddy managed command task.')
    return {'harness': 'workbuddy_task', 'session_id': session}


def complete(target, message):
    current = environment_target()
    require(current is not None and all(target.get(k) == value for k, value in current.items()),
            'session_mismatch', 'WorkBuddy managed task belongs to a different session.')
    # No external message is dispatched. Returning from the host's pending
    # TaskOutput continues its desktop request with normal UI routing.
    return {'status': 'awaiting_task', 'transport': 'managed_task_output'}
