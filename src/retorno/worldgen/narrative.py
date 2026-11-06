"""Opt-in narrative-world-v1 compiler; uses the productive historical manifest.

This is a finite data contract, not a general constraint solver. Nothing here
publishes knowledge or activates directories outside the installed catalogue.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
import random
import re

from retorno.model.world import region_for_pos, sector_id_for_pos
from retorno.runtime import data_loader as data

CONTRACT_VERSION = "narrative-world-v1"
KINDS = {"station", "relay", "waystation", "ship", "derelict"}


class ContentError(ValueError):
    def __init__(self, source, entity, field, cause, status="invalid"):
        self.status = status
        self.source, self.entity, self.field, self.cause = source, entity, field, cause
        super().__init__(f"{status}: {source} :: {entity} :: {field}: {cause}")


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def fingerprint(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def collect_catalog():
    """Capture only actual loader roots, including every indexed single/text."""
    records = []
    for kind, directory, id_key in (("locations", "locations", None), ("arcs", "arcs", "arc_id")):
        try:
            definitions = data.load_definition_records(directory)
        except ValueError as exc:
            raise ContentError(directory, "package", "json", str(exc)) from exc
        for source, value in definitions:
            try:
                ident = value.get(id_key) if id_key else value.get("node", {}).get("node_id")
                if not isinstance(ident, str) or not ident:
                    raise ValueError("missing package identity")
            except (ValueError, OSError, AttributeError) as exc:
                raise ContentError(source, "package", "json/identity", str(exc)) from exc
            records.append(dict(kind=kind, id=ident, source=source, value=value))
    index = data._DATA_ROOT / "lore/singles/index.json"
    if index.exists():
        try:
            singles = data.load_singles()
            if not isinstance(singles, list):
                raise ValueError("list required")
            for value in singles:
                ident = value.get("single_id")
                if not isinstance(ident, str) or not ident:
                    raise ValueError("missing single_id")
                records.append(dict(kind="singles", id=ident, source="lore/singles/index.json", value=value))
        except (ValueError, OSError, AttributeError) as exc:
            raise ContentError("lore/singles/index.json", "package", "json/identity", str(exc)) from exc
    records.sort(key=lambda r: (r["kind"], r["id"], r["source"]))
    seen = set()
    texts = {}

    def read_refs(value, record, field=""):
        if isinstance(value, list):
            for i, entry in enumerate(value):
                read_refs(entry, record, f"{field}[{i}]")
        elif isinstance(value, dict):
            for key, entry in value.items():
                at = f"{field}.{key}"
                if key in {"content_ref", "content_ref_en", "content_ref_es"}:
                    if not isinstance(entry, str) or not entry:
                        raise ContentError(record["source"], record["id"], at, "nonempty relative path required")
                    path = (data._DATA_ROOT / entry).resolve()
                    if not path.is_relative_to(data._DATA_ROOT.resolve()):
                        raise ContentError(record["source"], record["id"], at, "path outside data root")
                    try:
                        texts[entry] = path.read_text(encoding="utf-8")
                    except OSError as exc:
                        raise ContentError(record["source"], record["id"], at, f"missing resource {entry}") from exc
                else:
                    read_refs(entry, record, at)

    for record in records:
        key = (record["kind"], record["id"])
        if key in seen:
            raise ContentError(record["source"], record["id"], "identity", "duplicate package")
        seen.add(key)
        read_refs(record["value"], record)
    return dict(records=records, texts=texts)


def validate_catalog(state):
    snapshot = state.world.narrative_snapshot
    if not snapshot:
        raise ContentError("save", "catalog", "snapshot", "missing narrative snapshot / falta el snapshot narrativo")
    if fingerprint(collect_catalog()) != snapshot["catalog_key"]:
        raise ContentError("installed catalog", "save", "catalog_key", "catalog changed; restore the installed packages / catálogo modificado; restaura los paquetes instalados")


def records_for(state, kind, fallback):
    snapshot = state.world.narrative_snapshot
    if not snapshot:
        return fallback()
    if not snapshot["declarations"] and not snapshot.get("radio_emitters"):
        # Legacy loaders remain domain injection points. Guard real installed
        # files before using them; templates do not become active by this path.
        validate_catalog(state)
        return fallback()
    return deepcopy(snapshot[kind])


def content_for(state, content_ref):
    if not content_ref:
        return ""
    snapshot = state.world.narrative_snapshot
    if snapshot and content_ref in snapshot["texts"]:
        return snapshot["texts"][content_ref]
    return None


def _fields(value, allowed, source, entity, field):
    if not isinstance(value, dict):
        raise ContentError(source, entity, field, "object required")
    unknown = set(value) - set(allowed)
    if unknown:
        raise ContentError(source, entity, field, f"unsupported fields {sorted(unknown)}")


def _list(value, source, entity, field):
    if not isinstance(value, list):
        raise ContentError(source, entity, field, "list required")
    return value


def _number(value, source, entity, field):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ContentError(source, entity, field, "finite number required")
    return float(value)


def compile_catalog(seed, catalog=None, *, search_budget=4096):
    """Deterministic finite backtracking over declared fixed/box/offset sites.

    Exhausting the trial budget is not a proof of unsatisfiability. Explicit
    links are validation-only: v1 never overrides the productive topology.
    """
    from retorno.worldgen.manifest import authored_base, define_manifest, new_session
    catalog = collect_catalog() if catalog is None else deepcopy(catalog)
    catalog["records"].sort(key=lambda r: (r["kind"], r["id"], r["source"]))
    def finite_fields(value, record, field=""):
        if isinstance(value, dict):
            for key, entry in value.items():
                finite_fields(entry, record, f"{field}.{key}")
        elif isinstance(value, list):
            for index, entry in enumerate(value):
                finite_fields(entry, record, f"{field}[{index}]")
        elif isinstance(value, float) and not math.isfinite(value):
            raise ContentError(record["source"], record["id"], field, "finite number required")
    for record in catalog["records"]:
        finite_fields(record["value"], record)
    catalog_key = fingerprint(catalog)
    from retorno.worldgen.radio import physical_catalog
    physical_catalog_key = fingerprint(physical_catalog(catalog))
    locations, arcs, singles = [], [], []
    entities, aliases, references, relations = {}, {}, [], []
    owners = {}

    def alias(token, ident, source):
        if not isinstance(token, str) or not token.strip():
            raise ContentError(source, ident, "aliases", "nonempty name required")
        norm = token.casefold()
        if norm in aliases and aliases[norm] != ident:
            raise ContentError(source, ident, "aliases", f"ambiguous {token!r}: {aliases[norm]}")
        aliases[norm] = ident

    def register(ident, declaration, source, base=False):
        if not isinstance(ident, str) or not re.fullmatch(r"[A-Z][A-Z0-9_]*", ident):
            raise ContentError(source, str(ident), "id", "uppercase stable ID required")
        if ident in entities:
            raise ContentError(source, ident, "id", f"duplicate physical declaration; use references ({owners[ident]})")
        if not base and ident == "RETORNO_SHIP":
            raise ContentError(source, ident, "id", "reserved player ship")
        entities[ident], owners[ident] = declaration, source
        alias(ident, ident, source)
        if declaration.get("name"):
            alias(declaration["name"], ident, source)
        for token in _list(declaration.get("aliases", []), source, ident, "aliases"):
            alias(token, ident, source)

    blocks = []
    for record in sorted(catalog["records"], key=lambda r: (r["kind"], r["id"])):
        value, source = record["value"], f"{record['kind']}:{record['id']} ({record['source']})"
        {"locations": locations, "arcs": arcs, "singles": singles}[record["kind"]].append(value)
        if record["kind"] == "locations":
            cfg = value["node"]
            register(cfg["node_id"], dict(name=cfg.get("name"), aliases=value.get("aliases", []),
                kind=cfg.get("kind", "unknown"), position={"fixed_ly": [cfg.get(f"{a}_ly", 0) for a in "xyz"]}, location=value), source, True)
        block = value.get("world_requirements")
        if block is not None:
            _fields(block, {"version", "entities", "references", "relations", "claims"}, source, record["id"], "world_requirements")
            if block.get("version") != CONTRACT_VERSION:
                raise ContentError(source, record["id"], "version", "unsupported contract")
            for field in ("entities", "references", "relations", "claims"):
                _list(block.get(field, []), source, record["id"], field)
            blocks.append((source, block))
    for source, block in blocks:
        for declaration in block.get("entities", []):
            _fields(declaration, {"id", "name", "aliases", "kind", "position"}, source, "entity", "entities")
            ident = declaration.get("id")
            if declaration.get("kind") not in KINDS:
                raise ContentError(source, str(ident), "kind", "unsupported physical kind")
            register(ident, declaration, source)
        references.extend((source, ref) for ref in block.get("references", []))
        relations.extend((source, rel) for rel in block.get("relations", []))

    def resolve(token, source, field):
        if not isinstance(token, str) or token.casefold() not in aliases:
            raise ContentError(source, str(token), field, "missing physical entity")
        return aliases[token.casefold()]

    for source, ref in references:
        resolve(ref, source, "references")
    normalized = []
    for source, rel in relations:
        _fields(rel, {"type", "from", "to", "min_ly", "max_ly", "from_kind", "to_kind"}, source, "relation", "relations")
        left, right = (resolve(rel.get(k), source, k) for k in ("from", "to"))
        kind = rel.get("type")
        if kind not in {"near", "physical_link", "historical_association"} or left == right:
            raise ContentError(source, left, "type", "unsupported relation or self relation")
        for side, ident in (("from", left), ("to", right)):
            if rel.get(side + "_kind") and entities[ident]["kind"] != rel[side + "_kind"]:
                raise ContentError(source, ident, side + "_kind", "incompatible endpoint type")
            if ident == "RETORNO_SHIP":
                raise ContentError(source, ident, side, "player ship is not a historical destination")
        result = dict(rel, **{"from": left, "to": right, "source": source})
        if kind == "near":
            lo = _number(rel.get("min_ly", 0), source, left, "min_ly")
            hi = _number(rel.get("max_ly"), source, left, "max_ly")
            if lo < 0 or hi < lo:
                raise ContentError(source, left, "near", "impossible distance interval", "unsatisfiable")
            result.update(min_ly=lo, max_ly=hi)
        elif "min_ly" in rel or "max_ly" in rel:
            raise ContentError(source, left, "relations", "distance fields require near")
        normalized.append(result)
    normalized.sort(key=canonical)
    positions, choices, dependencies = {}, {}, {}
    for ident, entity in sorted(entities.items()):
        source, pos = owners[ident], entity.get("position")
        _fields(pos, {"fixed_ly", "box_ly", "offset_from", "offset_box_ly", "sector", "regions_any"}, source, ident, "position")
        modes = [k for k in ("fixed_ly", "box_ly", "offset_box_ly") if k in pos]
        if len(modes) != 1:
            raise ContentError(source, ident, "position", "exactly one fixed/box/offset mode required")
        mode = modes[0]
        raw = pos[mode]
        if not isinstance(raw, list) or len(raw) != 3:
            raise ContentError(source, ident, mode, "three axes required")
        if mode == "fixed_ly":
            candidates = [tuple(_number(v, source, ident, mode) for v in raw)]
        else:
            bounds = []
            for axis in raw:
                if not isinstance(axis, list) or len(axis) != 2:
                    raise ContentError(source, ident, mode, "[min,max] per axis required")
                lo, hi = [_number(v, source, ident, mode) for v in axis]
                if hi < lo:
                    raise ContentError(source, ident, mode, "inverted interval", "unsatisfiable")
                bounds.append((lo, hi))
            rng = random.Random(int(fingerprint((CONTRACT_VERSION, seed, ident)), 16))
            candidates = [tuple(rng.uniform(lo, hi) for lo, hi in bounds) for _ in range(32)]
        if mode == "offset_box_ly":
            dependencies[ident] = resolve(pos.get("offset_from"), source, "offset_from")
        elif "offset_from" in pos:
            raise ContentError(source, ident, "offset_from", "requires offset_box_ly")
        if "sector" in pos:
            from retorno.worldgen.generator import _parse_sector_id
            try:
                _parse_sector_id(pos["sector"])
            except (ValueError, TypeError) as exc:
                raise ContentError(source, ident, "sector", "canonical sector required") from exc
        if "regions_any" in pos and (not isinstance(pos["regions_any"], list) or not pos["regions_any"] or not all(isinstance(r, str) and r in {"disk", "bulge", "halo"} for r in pos["regions_any"])):
            raise ContentError(source, ident, "regions_any", "nonempty canonical regions required")
        choices[ident] = candidates
    order, pending = [], set(entities)
    while pending:
        ready = sorted(i for i in pending if dependencies.get(i) not in pending)
        if not ready:
            raise ContentError("catalog", ",".join(sorted(pending)), "offset_from", "cyclic position dependencies")
        order.extend(ready)
        pending.difference_update(ready)
    # Prove contradictions on fixed endpoints without searching unrelated
    # variable entities. Sampling failure alone never proves impossibility.
    for rel in normalized:
        a, b = rel["from"], rel["to"]
        if a in dependencies or b in dependencies or len(choices[a]) != 1 or len(choices[b]) != 1:
            continue
        distance = math.dist(choices[a][0], choices[b][0])
        impossible = rel["type"] == "near" and not rel["min_ly"] <= distance <= rel["max_ly"]
        if impossible or (rel["type"] == "physical_link" and distance > 45):
            raise ContentError(rel["source"], f"{a}->{b}", rel["type"], "fixed endpoints contradict the physical requirement", "unsatisfiable")
    trials = 0
    solved_definition = None

    def solve(index):
        nonlocal trials, solved_definition
        if index == len(order):
            compiled_locations = list(locations)
            for ident, entity in sorted(entities.items()):
                if "location" in entity:
                    continue
                compiled_locations.append(dict(node=dict(node_id=ident, name=entity.get("name", ident), kind=entity["kind"],
                    **dict(zip(("x_ly", "y_ly", "z_ly"), positions[ident]))), aliases=entity.get("aliases", [])))
            compiled_locations = [loc for loc in compiled_locations if loc["node"]["node_id"] != "RETORNO_SHIP"]
            definition = define_manifest(seed, authored=authored_base(compiled_locations), narrative_key=physical_catalog_key if blocks else "")
            session = new_session(definition)
            for rel in normalized:
                if rel["type"] != "physical_link":
                    continue
                a, b = rel["from"], rel["to"]
                if math.dist(positions[a], positions[b]) > definition.hop_cap_ly:
                    return False
                from retorno.worldgen.manifest import SiteIdentity
                ai, bi = (SiteIdentity(definition.scope, "authored", i) for i in (a, b))
                sa, sb = (session.sector(sector_id_for_pos(*positions[i])) for i in (a, b))
                edges = list(sa.internal_edges)
                if sa.sector_id != sb.sector_id and sb.sector_id in session.ranked(sa.sector_id):
                    if sa.topology_hub == ai and sb.topology_hub == bi:
                        continue
                if not any({e.left, e.right} == {ai, bi} for e in edges):
                    return False
            solved_definition = definition
            return True
        ident = order[index]
        pos = entities[ident]["position"]
        for candidate in choices[ident]:
            trials += 1
            if trials > search_budget:
                raise ContentError(owners[ident], ident, "position/relations", "search budget exhausted; mandatory verification incomplete", "not_evaluated")
            origin = positions[dependencies[ident]] if ident in dependencies else (0, 0, 0)
            xyz = tuple(v + o for v, o in zip(candidate, origin))
            if not all(math.isfinite(v) for v in xyz):
                raise ContentError(owners[ident], ident, "position", "nonfinite result")
            from retorno.worldgen.manifest import MAX_SECTOR_INDEX
            if any(abs(v / 10) > MAX_SECTOR_INDEX - 4 for v in xyz):
                raise ContentError(owners[ident], ident, "position", "outside certified coordinate domain")
            positions[ident] = xyz
            if pos.get("sector") and sector_id_for_pos(*xyz) != pos["sector"]:
                continue
            if pos.get("regions_any") and region_for_pos(*xyz) not in pos["regions_any"]:
                continue
            ok = True
            for rel in normalized:
                a, b = rel["from"], rel["to"]
                if rel["type"] == "near" and a in positions and b in positions:
                    dist = math.dist(positions[a], positions[b])
                    if not rel["min_ly"] <= dist <= rel["max_ly"]:
                        ok = False
                        break
            if ok and solve(index + 1):
                return True
        positions.pop(ident, None)
        return False

    if not solve(0):
        # A finite discretization cannot prove continuous boxes impossible.
        variable = any(len(c) > 1 for c in choices.values())
        raise ContentError("catalog", ",".join(sorted(entities)), "position/relations", "no verified placement in finite candidate domain", "not_evaluated" if variable else "unsatisfiable")
    extra_locations = []
    for ident, entity in sorted(entities.items()):
        if "location" not in entity:
            extra_locations.append(dict(node=dict(node_id=ident, name=entity.get("name", ident), kind=entity["kind"],
                **dict(zip(("x_ly", "y_ly", "z_ly"), positions[ident]))), aliases=entity.get("aliases", [])))
    locations.extend(extra_locations)

    def bind(value, source):
        if isinstance(value, list):
            return [bind(v, source) for v in value]
        if not isinstance(value, dict):
            return value
        result = {k: bind(v, source) for k, v in value.items()}
        bindings = value.get("spatial_bindings")
        if bindings is None:
            return result
        _fields(bindings, {"version", "values"}, source, "bindings", "spatial_bindings")
        if bindings.get("version") != CONTRACT_VERSION:
            raise ContentError(source, "bindings", "version", "unsupported binding version")
        if not isinstance(bindings.get("values", {}), dict):
            raise ContentError(source, "bindings", "values", "object required")
        replacements = {}
        for token, binding in bindings.get("values", {}).items():
            _fields(binding, {"entity", "field"}, source, token, "binding")
            ident = resolve(binding.get("entity"), source, "binding.entity")
            xyz = positions[ident]
            fields = {"id": ident, "sector": sector_id_for_pos(*xyz), "coord": ", ".join(repr(x) for x in xyz)}
            if not re.fullmatch(r"[a-z][a-z0-9_]*", token) or binding.get("field") not in fields:
                raise ContentError(source, token, "binding.field", "unsupported token or field")
            replacements["{{" + token + "}}"] = fields[binding["field"]]

        def render(text):
            for token, replacement in replacements.items():
                text = text.replace(token, replacement)
            return text

        if "line" in result:
            result["line"] = render(str(result["line"]))
        for ref_key in ("content_ref", "content_ref_en", "content_ref_es"):
            refs = [result] + list(result.get("files", []))
            for ref_entry in refs:
                ref = ref_entry.get(ref_key)
                if ref:
                    # Private content addresses isolate distinct bindings of a shared template.
                    new_ref = "compiled:" + fingerprint((source, ref, replacements))
                    bound_texts[new_ref] = render(bound_texts[ref])
                    text_paths[new_ref] = text_paths[ref]
                    ref_entry[ref_key] = new_ref
        if "content" in result:
            result["content"] = render(str(result["content"]))
        return result

    bound_texts = dict(catalog["texts"])
    text_paths = {ref: ref for ref in bound_texts}
    snapshot = dict(version=CONTRACT_VERSION, catalog_key=catalog_key, physical_catalog_key=physical_catalog_key, seed=seed,
        sources={f"{ {'arcs': 'arc', 'singles': 'single', 'locations': 'location'}[r['kind']]}:{r['id']}": r["source"] for r in catalog["records"]},
        locations=[bind(v, "location:" + v["node"]["node_id"]) for v in locations],
        arcs=[bind(v, "arc:" + v["arc_id"]) for v in arcs],
        singles=[bind(v, "single:" + v["single_id"]) for v in singles],
        texts=bound_texts, aliases=aliases, positions=positions, relations=normalized,
        declarations=blocks, reservations={},
        relation_results=[dict(type=rel["type"], **{"from": rel["from"], "to": rel["to"]},
            distance_ly=math.dist(positions[rel["from"]], positions[rel["to"]]), status="certified") for rel in normalized])
    # Freeze authored content refs too, matching load_locations' inline semantics.
    for loc in snapshot["locations"]:
        for entry in loc.get("fs_files", []):
            if entry.get("content_ref") and "content" not in entry:
                entry["content"] = bound_texts[entry["content_ref"]]

    def validate_tokens(value, source, field=""):
        if isinstance(value, list):
            for index, entry in enumerate(value):
                validate_tokens(entry, source, f"{field}[{index}]")
        elif isinstance(value, dict):
            for key, entry in value.items():
                at = f"{field}.{key}" if field else key
                if key in {"content_ref", "content_ref_en", "content_ref_es"}:
                    text = bound_texts[entry]
                    at += f" ({text_paths[entry]})"
                elif key in {"content", "line"} and isinstance(entry, str):
                    text = entry
                else:
                    validate_tokens(entry, source, at)
                    continue
                token = re.search(r"\{\{[a-z][a-z0-9_]*\}\}", text)
                if token:
                    raise ContentError(source, "bindings", at, f"unbound spatial token {token[0]}")

    # Validate effective document fields even when no renderer was invoked.
    # Waiting until all bindings are applied also permits a parent document's
    # bindings to resolve templates referenced by its `files` entries.
    for kind, prefix in (("locations", "location"), ("arcs", "arc"), ("singles", "single")):
        for value in snapshot[kind]:
            ident = value["node"]["node_id"] if kind == "locations" else value[prefix + "_id"]
            package = f"{prefix}:{ident}"
            source = snapshot["sources"].get(package, owners.get(ident, "catalog"))
            validate_tokens(value, f"{package} ({source})")
    from retorno.worldgen.radio import compile_radio
    compile_radio(solved_definition, snapshot)
    return solved_definition, snapshot


def prepare_new_world(state):
    definition, snapshot = compile_catalog(state.meta.rng_seed)
    state.world.narrative_snapshot = snapshot
    # Preserve seed selection before materialization for catalogues without new
    # physical declarations. Requirement-bearing universes are pinned now.
    if snapshot["declarations"]:
        state.world.manifest_definition = definition
    state.world.universe_rules_key = definition.rules_key
    from retorno.core.lore import validate_essential_opportunities
    validate_essential_opportunities(state, definition)
