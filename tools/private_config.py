"""Read only the two provider keys from an owner-only local .env file."""
import os
from pathlib import Path
import stat


class ConfigError(Exception):
    pass


def load_keys(path):
    path = Path(path)
    flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0)
    try:
        fd = os.open(path, flags)
        with os.fdopen(fd, 'rb') as f:
            info = os.fstat(f.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077 or info.st_uid != os.geteuid():
                raise ConfigError('The .env file must be owned by you and accessible only to you (mode 600).')
            raw = f.read(8193)
    except OSError:
        raise ConfigError('Cannot open the private .env file.') from None
    if len(raw) > 8192:
        raise ConfigError('The .env file is too large.')
    try:
        lines = raw.decode('utf-8').splitlines()
    except UnicodeDecodeError:
        raise ConfigError('The .env file must be UTF-8 text.') from None
    names = {'VENICE_API_KEY', 'SURPLUS_API_KEY'}
    found = {}
    for line in lines:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        name, sep, value = line.partition('=')
        name = name.strip()
        if name not in names:
            continue
        if not sep or name in found:
            raise ConfigError('A provider key is malformed or repeated in .env.')
        value = value.strip()
        if value and value[0] in "'\"":
            if len(value) < 2 or value[-1] != value[0]:
                raise ConfigError('A provider key has unmatched quotes in .env.')
            value = value[1:-1]
        if not 10 <= len(value) <= 255 or any(ord(c) < 33 or ord(c) > 126 for c in value):
            raise ConfigError('Both provider keys must be filled in without spaces or line breaks.')
        found[name] = value
    if set(found) != names:
        raise ConfigError('Fill both provider keys in .env before running this command.')
    return found
