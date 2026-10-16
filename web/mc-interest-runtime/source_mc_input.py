"""Read-only current-source MC input diagnostics for the local General worker."""
from pathlib import Path
import json,hashlib

AUTHORITY_SHA256='ca53d158123e9aba70f9e44a32eb2a8ff1ba795ea9039eba7afcd1b00bed841b'

def diagnose_request(request):
    # Source policies are trusted installed files. A request cannot replace
    # these policies, the codec, or the internally constructed receiver state.
    raw=(Path(__file__).resolve().parent/'source-mc-authority.json').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=AUTHORITY_SHA256:
        raise ValueError('Installed source diagnostic authority changed')
    authority=json.loads(raw)
    if authority.get('format')!='tax-reborn-owned-current-MC-authority-v1':
        raise ValueError('Unsupported installed source diagnostic authority')
    from source_mc.source_current_supplier import read_owned_request
    try:return read_owned_request(request,authority)
    except ValueError as error:
        # The shared worker exposes a short expected ValueError. Unexpected
        # exceptions remain generic through its existing error formatter.
        raise ValueError(str(error))from None
