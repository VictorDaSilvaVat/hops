"""
Shared input-sanitization helpers.

Blockchain addresses are used verbatim to build filesystem paths (report
folders/files) and are attacker/user-controlled. This guards against path
traversal (e.g. "../../etc/passwd") regardless of which chain-specific
format validator (if any) ran upstream.
"""
import re

from exceptions import ValidationError

_SAFE_PATH_COMPONENT_RE = re.compile(r'^[A-Za-z0-9]{1,128}$')


def safe_path_component(value: str, label: str = "address") -> str:
    """Raise ValidationError unless value is safe to use as a single path segment."""
    if not isinstance(value, str) or not _SAFE_PATH_COMPONENT_RE.match(value):
        raise ValidationError(
            f"Invalid {label}: must be 1-128 alphanumeric characters (got {value!r})"
        )
    return value
