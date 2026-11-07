"""Public projections of historical addresses; never a discovery authority.

The scope is implicit in a game. Signed sector coordinates are zigzag encoded
in base 36, followed by the historical slot. No digest is shortened and no
physical catalogue is queried. Only the command's acquired IDs may resolve.
"""
from __future__ import annotations

import builtins
from contextvars import ContextVar
from functools import wraps
import re


_OPERATIVE = re.compile(
    r"(?<![A-Za-z0-9])S([+-][0-9]+)_([+-][0-9]+)_([+-][0-9]+):WG1(?:C[1-9][0-9]*)?_([0-9a-f]{64})_([0-9]+)(?![A-Za-z0-9])"
)
_CERTIFICATE_LINE = re.compile(
    r"(?m)^(?:(?:Record / Registro|Record|Registro|Report ID|ID de informe): )?"
    r"(?:HI1:|HR1-record:)[0-9a-f]{64}\n?"
)
_output_state = ContextVar("location_output_state", default=None)


def _base36(value: int) -> str:
    alphabet = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    result = ""
    while value:
        value, digit = divmod(value, 36)
        result = alphabet[digit] + result
    return result or "0"


def _namespace(state, definition) -> str:
    reserved = {a.raw_id.casefold() for a in definition.authored} if definition else set()
    reserved.update(state.world.narrative_snapshot.get("aliases", {}))
    prefix = "P-"
    # Reserve a whole prefix against the finite immutable authored namespace.
    # Finite: the chosen prefix cannot outgrow the longest reserved identifier.
    while any(ident.startswith(prefix.casefold()) for ident in reserved):
        prefix += "-"
    return prefix


def public_node_id(state, node_id: str) -> str:
    match = _OPERATIVE.fullmatch(node_id)
    if not match:
        return node_id  # Includes legacy procedural and authored identifiers.
    from retorno.worldgen.generator import universe_definition
    definition = state.world.manifest_definition or universe_definition(state)
    if match[4] != definition.scope:
        return node_id
    reserved = {a.raw_id for a in definition.authored}
    if node_id in reserved:
        return node_id
    # Validate canonical spelling and the same authored collision escape as
    # manifest.operative_id, without lookup/materialization of a physical site.
    coords = tuple(int(match[i]) for i in (1, 2, 3))
    sid = "S" + "_".join(f"{v:+04d}" for v in coords)
    slot = int(match[5])
    attempt = 0
    candidate = f"{sid}:WG1_{definition.scope}_{slot}"
    while candidate in reserved:
        attempt += 1
        candidate = f"{sid}:WG1C{attempt}_{definition.scope}_{slot}"
    if candidate != node_id:
        return node_id
    parts = [_base36(2 * v if v >= 0 else -2 * v - 1) for v in coords]
    return _namespace(state, definition) + ".".join((*parts, _base36(slot)))


def resolve_public_id(state, token: str, acquired_ids) -> str | None:
    """No inverse-catalogue lookup: a guessed token grants no knowledge."""
    acquired = set(acquired_ids)
    if token in acquired:
        return token
    matches = {nid for nid in acquired if public_node_id(state, nid).casefold() == token.casefold()}
    return next(iter(matches)) if len(matches) == 1 else None


def public_text(state, text: str, *, certificates: bool = False) -> str:
    """Project only references already authorized by the caller's renderer.

    This does not consult nodes, pools, radio candidates or hidden placements.
    The original document is still the sole input to import and validation.
    """
    text = _OPERATIVE.sub(lambda match: public_node_id(state, match[0]), text)
    return text if certificates else _CERTIFICATE_LINE.sub("", text)


def restore_public_references(state, text: str, authorized_ids) -> str:
    """Reverse a view using its exact finite source references, not a catalogue."""
    aliases = {public_node_id(state, nid): nid for nid in authorized_ids}
    if not aliases:
        return text
    pattern = re.compile(r"(?<![\w.-])(?:" + "|".join(
        re.escape(alias) for alias in sorted(aliases, key=len, reverse=True)
    ) + r")(?![\w.-])")
    return pattern.sub(lambda match: aliases[match[0]], text)


def resolve_public_path(state, path: str) -> str:
    if path in state.os.fs:
        return path
    matches = [raw for raw in state.os.fs if public_text(state, raw) == path]
    return matches[0] if len(matches) == 1 else path


def public_output(func):
    """Scope the REPL's local print function without changing global stdout.

    ContextVar keeps concurrent/nested renderers isolated. Debug renderers are
    deliberately undecorated and retain technical identifiers/certificates.
    """
    @wraps(func)
    def render(state, *args, **kwargs):
        token = _output_state.set(state)
        try:
            return func(state, *args, **kwargs)
        finally:
            _output_state.reset(token)
    return render


def print_public(*args, **kwargs):
    state = _output_state.get()
    if state is not None:
        args = tuple(public_text(state, str(arg)) for arg in args)
    builtins.print(*args, **kwargs)
