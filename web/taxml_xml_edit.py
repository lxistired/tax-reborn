"""Edit validated leaf text without serializing or changing other XML bytes.

This independent helper is not a native return writer or a recalculation engine.
The caller must validate the source, registry, field type and review context.
"""
from xml.parsers import expat
import taxml_wire as wire


def _name(value):
    return '{' + value if '}' in value else value


def _escape(value):
    if not isinstance(value, str) or len(value) > 4096:
        raise ValueError('Invalid corrected XML text.')
    if any(not (c in '\t\n\r' or '\x20' <= c <= '\ud7ff' or '\ue000' <= c <= '\ufffd'
                or '\U00010000' <= c <= '\U0010ffff') for c in value):
        raise ValueError('Invalid XML character in corrected text.')
    return value.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('\r', '&#13;').encode('utf-8')


def patch_text_nodes(data, replacements):
    """Replace exact ET-compatible paths; every byte outside spans is retained."""
    wire.xml(data)
    if not isinstance(replacements, dict) or not 1 <= len(replacements) <= 100:
        raise ValueError('Select explicit XML leaf edits.')
    for item in replacements.values():
        if not isinstance(item, dict) or set(item) != {'qname', 'text', 'replacement'}:
            raise ValueError('Invalid bound XML edit.')
        _escape(item['replacement'])
    parser = expat.ParserCreate(namespace_separator='}')
    stack, found = [], {}

    def start(name, attrs):
        index = parser.CurrentByteIndex
        if stack:
            parent = stack[-1]
            path = (parent['path'] + '/' if parent['path'] else '') + str(parent['children'])
            parent['children'] += 1
        else:
            path = ''
        quote = None
        end = index
        while end < len(data):
            character = data[end]
            if quote is not None:
                if character == quote:
                    quote = None
            elif character in (34, 39):
                quote = character
            elif character == 62:
                break
            end += 1
        stack.append({'path': path, 'qname': _name(name), 'start': end + 1,
                      'self_closing': data[index:end].rstrip().endswith(b'/'),
                      'children': 0, 'text': []})

    def text(value):
        if stack:
            stack[-1]['text'].append(value)

    def opaque(*args):
        if stack:
            stack[-1]['children'] += 1  # ElementTree preserves comments and PIs.

    def end(name):
        node = stack.pop()
        path = node['path']
        if path not in replacements:
            return
        item = replacements[path]
        if node['children'] or node['self_closing'] or node['qname'] != item['qname'] or ''.join(node['text']) != item['text']:
            raise ValueError('Source XML leaf no longer matches the reviewed field.')
        found[path] = (node['start'], parser.CurrentByteIndex, _escape(item['replacement']))

    parser.StartElementHandler = start
    parser.EndElementHandler = end
    parser.CharacterDataHandler = text
    parser.CommentHandler = opaque
    parser.ProcessingInstructionHandler = opaque
    parser.Parse(data, True)
    if set(found) != set(replacements):
        raise ValueError('A reviewed XML leaf was not found.')
    result = data
    for begin, finish, replacement in sorted(found.values(), reverse=True):
        result = result[:begin] + replacement + result[finish:]
    root = wire.xml(result)
    for path, item in replacements.items():
        element = root
        try:
            for component in path.split('/') if path else []:
                element = element[int(component)]
        except (ValueError, IndexError):
            raise ValueError('Corrected XML path changed.') from None
        if element.tag != item['qname'] or (element.text or '') != item['replacement'] or list(element):
            raise ValueError('Corrected XML readback differs from the requested field.')
    return result
