"""Make the integration importable without a Home Assistant install.

The pure modules (protocol, transport, client) carry no Home Assistant imports,
and the package ``__init__`` keeps its HA imports lazy, so ``dpremote.protocol``
& friends import cleanly against a bare Python interpreter.
"""

import pathlib
import sys

_CC = pathlib.Path(__file__).resolve().parents[1] / "custom_components"
sys.path.insert(0, str(_CC))
