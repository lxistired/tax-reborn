"""Independent ordered literal transform selection, before named/default work.

Later instance presence, metadata and TPS writeback are outside this model.
"""
from dataclasses import dataclass


def _text(value):
    if not isinstance(value, str):
        raise ValueError('explicit text required')
    try:
        data = value.encode('utf-8')
    except UnicodeEncodeError as exc:
        raise ValueError('valid UTF8 scalar text required') from exc
    if len(data) > 65536:
        raise ValueError('bounded text profile required')


@dataclass(frozen=True)
class Selection:
    action: str
    value: str
    match_index: object = None
    transform_name: str = ''


def select_transform(text, pairs, *, direction, transform_name=''):
    _text(text)
    _text(transform_name)
    if type(direction) is not int or direction not in (0, 1):
        raise ValueError('explicit direction0/1 required')
    if not isinstance(pairs, (list, tuple)) or len(pairs) > 10000:
        raise ValueError('bounded explicit ordered pair list required')
    for pair in pairs:
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            raise ValueError('every pair must contain MEF and TPS text')
        _text(pair[0])
        _text(pair[1])
    if pairs:
        source, destination = (0, 1) if direction == 1 else (1, 0)
        for index, pair in enumerate(pairs):
            if text.encode('utf-8') == pair[source].encode('utf-8'):
                return Selection('literal_match', pair[destination], index)
        # A nonempty list suppresses named/default work even with no match.
        return Selection('literal_passthrough', text)
    if transform_name:
        return Selection('named', text, transform_name=transform_name)
    return Selection('default', text)
