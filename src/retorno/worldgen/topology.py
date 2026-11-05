"""Finite, maximal budgeted matching of historical sector hubs.

The king grid's four undirected directions each split into two disjoint
matchings by parity. Eight ordered rounds consider every potential pair once.
A rejected candidate has a full endpoint which remains full: the result is
maximal, respects both budgets, and needs at most eight dependency hops.
All memoization belongs to a single query session.
"""
from __future__ import annotations

from retorno.worldgen.generator import _neighbor_sector_ids_2d, _parse_sector_id, _pair_key
from retorno.worldgen.manifest import _Session

_DIRECTIONS = ((1, 0), (0, 1), (1, 1), (1, -1))


class ColoredSession(_Session):
    def __init__(self, definition):
        super().__init__(definition)
        self.colors = tuple(range(8))
        self.degrees = {}
        self.acceptances = {}
        self.candidates = {}
        # Preserve the canonical first origin request before assigning outer
        # exits. This is a fixed historical rule, not a runtime rescue.
        self.initial = set(_neighbor_sector_ids_2d("S+000_+000_+000"))
        self.initial_edges = set()
        self.initial_degrees = {sid: 0 for sid in self.initial}
        pairs = {tuple(sorted((sid, other))) for sid in self.initial
                 for other in _neighbor_sector_ids_2d(sid, include_self=False) if other in self.initial}
        for left, right in sorted(pairs, key=lambda p: _pair_key(*p)):
            if self.candidate(left, right) and all(self.initial_degrees[sid] < int(
                self.archetypes[self.sector(sid).archetype]["intersector_link_max"]) for sid in (left, right)):
                self.initial_edges.add((left, right))
                self.initial_degrees[left] += 1
                self.initial_degrees[right] += 1

    def candidate(self, left, right):
        key = tuple(sorted((left, right)))
        if key not in self.candidates:
            self.candidates[key] = super().candidate(*key)
        return self.candidates[key]

    def partner(self, sid, phase):
        x, y, z = _parse_sector_id(sid)
        color = self.colors[phase]
        dx, dy = _DIRECTIONS[color // 2]
        step = 1 if (x if dx else y) % 2 == color % 2 else -1
        return f"S{x+step*dx:+04d}_{y+step*dy:+04d}_{z:+04d}"

    def degree_before(self, sid, phase):
        if phase == 0:
            return self.initial_degrees.get(sid, 0)
        key = sid, phase
        if key not in self.degrees:
            self.degrees[key] = self.degree_before(sid, phase-1) + self.accepted(sid, phase-1)
        return self.degrees[key]

    def accepted(self, sid, phase):
        other = self.partner(sid, phase)
        key = tuple(sorted((sid, other)))
        if sid in self.initial and other in self.initial:
            return False  # Already accounted for in the immutable initial pass.
        if key not in self.acceptances:
            allowed = bool(self.candidate(sid, other))
            if allowed:
                for endpoint in key:
                    cap = int(self.archetypes[self.sector(endpoint).archetype]["intersector_link_max"])
                    if self.degree_before(endpoint, phase) >= cap:
                        allowed = False
                        break
            self.acceptances[key] = allowed
        return self.acceptances[key]

    def ranked(self, sid):
        if sid not in self.rankings:
            selected = {self.partner(sid, phase) for phase in range(8) if self.accepted(sid, phase)}
            selected.update(b if a == sid else a for a, b in self.initial_edges if sid in (a, b))
            self.rankings[sid] = tuple(sorted(selected))
        return self.rankings[sid]

