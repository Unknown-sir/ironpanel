import secrets
import string

from ..core.models import AppSetting

DEFAULT_LENGTH = 10
DEFAULT_MODE = 'both'
MIN_LENGTH = 3
MAX_LENGTH = 128
VALID_MODES = {'letters', 'numbers', 'both'}


def _setting(key, default=''):
    row = AppSetting.query.filter_by(key=key).first()
    if not row or row.value in (None, ''):
        return default
    return str(row.value)


def normalize_password_policy(length=None, mode=None):
    if length is None:
        length = _setting('auto_password_length', str(DEFAULT_LENGTH))
    try:
        length = int(length)
    except Exception:
        length = DEFAULT_LENGTH
    length = max(MIN_LENGTH, min(MAX_LENGTH, length))

    if mode is None:
        mode = _setting('auto_password_mode', DEFAULT_MODE)
    raw = str(mode or DEFAULT_MODE).strip().lower()
    aliases = {
        'letter': 'letters', 'alpha': 'letters', 'alphabet': 'letters', 'حرف': 'letters',
        'number': 'numbers', 'num': 'numbers', 'digit': 'numbers', 'digits': 'numbers', 'عدد': 'numbers', 'numeric': 'numbers',
        'mixed': 'both', 'alnum': 'both', 'letters_numbers': 'both', 'حرف_و_عدد': 'both',
    }
    raw = aliases.get(raw, raw)
    if raw not in VALID_MODES:
        raw = DEFAULT_MODE
    return length, raw


def generate_user_password(length=None, mode=None):
    length, mode = normalize_password_policy(length, mode)
    if mode == 'numbers':
        alphabet = string.digits
    elif mode == 'letters':
        alphabet = string.ascii_letters
    else:
        # Mixed means the resulting password actually contains both classes,
        # not merely that both classes were eligible during random selection.
        chars = [secrets.choice(string.ascii_letters), secrets.choice(string.digits)]
        alphabet = string.ascii_letters + string.digits
        chars.extend(secrets.choice(alphabet) for _ in range(length - 2))
        secrets.SystemRandom().shuffle(chars)
        return ''.join(chars)
    return ''.join(secrets.choice(alphabet) for _ in range(length))
