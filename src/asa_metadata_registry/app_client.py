from __future__ import annotations

from typing import Any

from .errors import MissingAppClientError


def import_generated_client() -> Any:
    """
    Import the generated ARC-56 AppClient module lazily.

    This keeps the rest of the SDK usable even if users only want box-reading features.
    """
    try:
        from .generated import asa_metadata_registry_client as mod
    except Exception as e:  # pragma: no cover
        raise MissingAppClientError(
            "Generated AppClient could not be imported. "
            "Ensure 'algokit-utils' is installed and the generated client is present."
        ) from e
    return mod
