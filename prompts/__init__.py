"""Format-specific prompt packs."""
from prompts import short

PACKS = {
    'short': short,
}


def get(format_name):
    if format_name not in PACKS:
        raise ValueError('No prompt pack for format: ' + format_name)
    return PACKS[format_name]
