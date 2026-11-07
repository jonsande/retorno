"""historical-radio-v1: pure equipment history and bounded physical discovery.

The authored compiler, radio physics and reception ledger remain in radio.py,
communications.py and WorldState. This kernel accepts no gameplay state or clock.
"""
from __future__ import annotations

from dataclasses import dataclass
import itertools
import json
import math

from retorno.config.balance import Balance
from retorno.model.world import RadioEmitter, RadioEmission
from retorno.worldgen import information, manifest
from retorno.worldgen.narrative import canonical, fingerprint

VERSION = "historical-radio-v1"
LEGACY_VERSION = "legacy-radio-v0"
KINDS = ("station", "relay", "waystation", "ship", "derelict")
CATEGORY = dict(station="station", relay="interstellar_relay", waystation="station",
    ship="emergency", derelict="emergency")
# Only emission density varies. Equipment and geography are identical in all profiles.
PROFILES = dict(sparse=.30, intermediate=.55, abundant=.80)


@dataclass(frozen=True, slots=True)
class RadioDefinition:
    version: str
    rules_json: str
    information_key: str
    explicit_hosts: tuple[str, ...]
    rules_key: str


@dataclass(frozen=True, slots=True)
class EquipmentState:
    installed: bool
    hardware: str
    powered: bool
    operational: bool


@dataclass(frozen=True, slots=True)
class RadioHistory:
    host: manifest.HistoricalSite
    rules_key: str
    emitter: RadioEmitter
    installed_t: float
    final_hardware: str
    failure_t: float | None
    energy_end_t: float | None
    emissions: tuple[RadioEmission, ...]
    message_kind: str | None
    source_record_id: str | None
    navigation_record: information.NavigationRecord | None

    def equipment_at(self, coordinate_t):
        if type(coordinate_t) not in (float, int) or not math.isfinite(coordinate_t):
            raise ValueError("Invalid equipment coordinate time")
        installed = coordinate_t >= self.installed_t
        hardware = ("not_installed" if not installed else self.final_hardware
            if self.failure_t is not None and coordinate_t >= self.failure_t else "serviceable")
        powered = installed and (self.energy_end_t is None or coordinate_t < self.energy_end_t)
        return EquipmentState(installed, hardware, powered, hardware == "serviceable" and powered)


@dataclass(frozen=True, slots=True)
class RadioPage:
    histories: tuple[RadioHistory, ...]
    cursor: dict
    complete: bool
    examined_sectors: int
    examined_sites: int


def _rules(profile):
    return dict(kernel="equipment-epochs-1-message-1", profile=profile,
        serviceable=dict(Balance.HISTORICAL_RADIO_SERVICEABLE),
        damaged=dict(Balance.HISTORICAL_RADIO_DAMAGED),
        powered=dict(Balance.HISTORICAL_RADIO_POWERED),
        emission_probability=PROFILES[profile], continuous_probability=.65,
        navigation_probability=.30, power={k: Balance.RADIO_POWER_BY_CATEGORY[CATEGORY[k]] for k in KINDS},
        sensitivity=dict(Balance.RADIO_SENSITIVITY), year_s=Balance.YEAR_S,
        installed_age_years=[150., 350.], failure_age_years=[.25, 25.],
        repeat_start_age_years=[30., 120.], finite_duration_years=[.02, 6.],
        hop_cap_ly=45.)


def define_radio(snapshot, information_definition, *, profile=None):
    profile = Balance.HISTORICAL_RADIO_PROFILE if profile is None else profile
    if profile not in PROFILES:
        raise ValueError("Unknown historical radio density profile")
    rules_json = canonical(_rules(profile))
    hosts = tuple(sorted({e.host_id for e in snapshot.get("radio_emitters", {}).values()}))
    key = fingerprint((VERSION, rules_json, information_definition.rules_key, hosts))
    return RadioDefinition(VERSION, rules_json, information_definition.rules_key, hosts, key)


def validate_definition(definition, information_definition, *, current=False):
    if (not isinstance(definition, RadioDefinition) or definition.version != VERSION
            or not isinstance(information_definition, information.InformationDefinition)
            or definition.information_key != information_definition.rules_key
            or definition.rules_key != fingerprint((VERSION, definition.rules_json,
                definition.information_key, definition.explicit_hosts))):
        raise ValueError("Historical radio definition mismatch / Definición de radio histórica incompatible")
    rules = json.loads(definition.rules_json)
    profile = rules.get("profile")
    if profile not in PROFILES:
        raise ValueError("Invalid historical radio profile")
    fixed = _rules(profile)
    parameters = {"serviceable", "damaged", "powered", "power", "sensitivity"}
    if (set(rules) != set(fixed) or any(rules[k] != fixed[k] for k in fixed if k not in parameters)
            or any(not isinstance(rules[k], dict) or set(rules[k]) != set(fixed[k]) for k in parameters)
            or any(type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 1
                for k in ("serviceable", "damaged", "powered") for v in rules[k].values())
            or any(rules["serviceable"][k]+rules["damaged"][k] > 1 for k in KINDS)
            or any(type(v) not in (int, float) or not math.isfinite(v) or v <= 0 for k in ("power", "sensitivity") for v in rules[k].values())
            or max(rules["power"].values()) > Balance.RADIO_MAX_POWER
            or canonical(rules) != definition.rules_json
            or definition.explicit_hosts != tuple(sorted(set(definition.explicit_hosts)))
            or (current and (profile != Balance.HISTORICAL_RADIO_PROFILE or rules != fixed))):
        raise ValueError("Historical radio rules changed / Reglas de radio histórica modificadas")
    return rules


def _draw(world, sampling_key, host, domain):
    # Independent SHA-256 domains: no Python hash, RNG state or draw ordering.
    return int(fingerprint((VERSION, world.scope, sampling_key,
        host.identity.encoded, domain))[:13], 16) / float(16**13)


def query_host(world, definition, information_definition, host_id, *, session=None):
    """Reproducible historical projection, including silent and destroyed radios.

    Explicit authored transmitters override the entire host (even emissions: []).
    Equipment times describe a coarse model, not electronic or population simulation.
    """
    rules = validate_definition(definition, information_definition)
    sampling_information = information.sampling_definition(information_definition)
    sampling_radio_key = fingerprint((VERSION, definition.rules_json,
        sampling_information.rules_key, definition.explicit_hosts))
    if world.algorithm_version != manifest.ALGORITHM_VERSION:
        raise ValueError("Historical radio requires certified physical history")
    session = session or manifest.new_session(world)
    host = manifest.resolve_operative_id(world, host_id, session=session)
    if host is None or host.kind not in KINDS or host_id in definition.explicit_hosts:
        return None
    sampling_key = fingerprint(({k: v for k, v in rules.items() if k not in {"profile", "emission_probability"}},
        sampling_information.rules_key, definition.explicit_hosts))
    draw = lambda domain: _draw(world, sampling_key, host, domain)
    year = rules["year_s"]
    age = lambda bounds, domain: -(bounds[0] + (bounds[1]-bounds[0])*draw(domain))*year
    installed = age(rules["installed_age_years"], "installed")
    roll = draw("conservation")
    preserved = rules["serviceable"][host.kind]
    hardware = "serviceable" if roll < preserved else "damaged" if roll < preserved+rules["damaged"][host.kind] else "destroyed"
    failure = None if hardware == "serviceable" else age(rules["failure_age_years"], "failure")
    energy_end = None if draw("energy") < rules["powered"][host.kind] else age(rules["failure_age_years"], "energy_end")
    emitter = RadioEmitter("@HR1:"+host_id, host_id, CATEGORY[host.kind], rules["power"][host.kind])
    emissions, message, record, source_record = (), None, None, None
    if draw("program_exists") < rules["emission_probability"]:
        mode = "continuous" if draw("mode") < rules["continuous_probability"] else "finite"
        # A separate scheduled stop permits intact, powered but silent equipment.
        stop = age(rules["failure_age_years"], "program_stop") if mode == "finite" or draw("program_ends") < .25 else None
        ends = [t for t in (failure, energy_end, stop) if t is not None]
        end = min(ends) if ends else None
        start = (age(rules["repeat_start_age_years"], "program_start") if mode == "continuous"
            else end - (rules["finite_duration_years"][0] + draw("duration")*
                (rules["finite_duration_years"][1]-rules["finite_duration_years"][0]))*year)
        # B1 owns every navigation candidate; absence never causes replacement.
        if draw("navigation") < rules["navigation_probability"]:
            archive = information.query_information(world, sampling_information, host_id)
            records = {r.record_id: r for r in archive.uplink}
            # Authored base files are testimony, even if they imitate B1 keys.
            # Only the B1 file producer's typed records certify a radio LINK.
            authored_files = json.loads(information_definition.authored_json).get(host_id, {}).get("files", [])
            for entry in (() if authored_files else archive.files):
                if entry.get("navigation_record"):
                    item = information.NavigationRecord(**entry["navigation_record"])
                    records[item.record_id] = item
            ordered = sorted(records.values(), key=lambda r: r.record_id)
            if ordered:
                record = ordered[min(len(ordered)-1, int(draw("navigation_slot")*len(ordered)))]
        eid = "@HR1:"+host_id+":0"
        if record:
            message, source_record = "navigation", record.record_id
            content = {locale: _navigation_text(record, locale) for locale in ("en", "es")}
        else:
            kinds = ("beacon", "telemetry", "technical", "distress", "warning", "route_archive", "ambient", "damaged_data")
            message = kinds[min(len(kinds)-1, int(draw("message")*len(kinds)))]
            if hardware == "destroyed" and draw("last_distress") < .35:
                message = "distress"
            source_record = "HR1-record:"+fingerprint((sampling_radio_key, host.identity.encoded, message))
            content = {locale: _environment_text(message, source_record, locale) for locale in ("en", "es")}
        channel = "station_broadcast" if host.kind in {"station", "relay", "waystation"} else "captured_signal"
        emissions = (RadioEmission(eid, emitter.emitter_id, mode, start, end, channel, content,
            navigation_link_to=record.destination_id if record else None),)
        if record and information.navigation_excluded(information_definition, host_id, record.destination_id):
            # The original program has no admissible payload: no replacement
            # destination, environmental message or retrospective emission.
            emissions, message, record, source_record = (), None, None, None
    return RadioHistory(host, definition.rules_key, emitter, installed, hardware, failure,
        energy_end, emissions, message, source_record, record)


def _navigation_text(record, locale):
    if locale == "es":
        kind = ("Conexión física histórica documentada." if record.kind == "historical_connection"
            else "Solución navegacional calculada; no acredita tráfico histórico.")
        return ("AVISO AUTOMÁTICO DE NAVEGACIÓN\nDatos antiguos; vigencia actual sin verificar.\n"
            f"Registro: {record.record_id}\n{kind}\nLINK: {record.source_id} -> {record.destination_id}\n")
    kind = ("Documented historical physical connection." if record.kind == "historical_connection"
        else "Calculated navigation solution; no evidence of historical traffic.")
    return ("AUTOMATED NAVIGATION NOTICE\nOld data; present validity unverified.\n"
        f"Record: {record.record_id}\n{kind}\nLINK: {record.source_id} -> {record.destination_id}\n")


def _environment_text(kind, record_id, locale):
    texts = {
        "beacon": ("Automatic identification cycle. Source identity cannot be decoded.", "Ciclo automático de identificación. No se puede decodificar la identidad de origen."),
        "telemetry": ("Recorded telemetry: clock drift exceeds tolerance. No current measurement is available.", "Telemetría grabada: deriva de reloj fuera de tolerancia. No hay medición actual disponible."),
        "technical": ("Recorded maintenance warning: standby circuit unavailable.", "Aviso de mantenimiento grabado: circuito de reserva no disponible."),
        "distress": ("Historical distress recording: loss of control reported. Present situation and survival unknown.", "Grabación histórica de socorro: pérdida de control declarada. Situación presente y supervivencia desconocidas."),
        "warning": ("Recorded navigation warning: approach markers unreliable. No usable coordinates remain.", "Advertencia navegacional grabada: marcadores de aproximación poco fiables. No quedan coordenadas utilizables."),
        "route_archive": ("Historical route announcement. Destination block unreadable; no navigation solution recovered.", "Anuncio de ruta histórica. Bloque de destino ilegible; no se ha recuperado solución navegacional."),
        "ambient": ("Automated carrier test. No navigation payload.", "Prueba automática de portadora. Sin datos de navegación."),
        "damaged_data": ("Damaged data fragment: [checksum incomplete]. No verified destination.", "Fragmento de datos deteriorado: [checksum incompleto]. Sin destino verificado."),
    }
    index = 1 if locale == "es" else 0
    header = ("AUTOMATED ARCHIVE SIGNAL\nRecording age and reliability uncertain. Reception does not establish present human activity."
        if locale == "en" else "SEÑAL AUTOMÁTICA DE ARCHIVO\nAntigüedad y fiabilidad inciertas. La recepción no acredita actividad humana actual.")
    return f"{header}\n{record_id}\n{texts[kind][index]}\n"


def local_domain(position, definition):
    if len(position) != 3 or not all(type(v) in (int, float) and math.isfinite(v) for v in position):
        raise ValueError("Invalid radio receiver coordinates")
    rules = json.loads(definition.rules_json)
    anchor = tuple(math.floor(v/10) for v in position)
    radius = math.ceil(math.sqrt(max(rules["power"].values())*max(rules["sensitivity"].values()))/10)
    offsets = sorted(itertools.product(range(-radius, radius+1), repeat=3), key=lambda p: (sum(v*v for v in p), p))
    sectors = tuple("S"+"_".join(f"{a+b:+04d}" for a,b in zip(anchor, delta)) for delta in offsets)
    return anchor, sectors


def query_local(world, definition, information_definition, position, *, cursor=None, limit=64, sector_budget=4):
    """One pure page of a complete local cube covering maximum reception range.

    Both physical cells and examined sites are bounded, including silent hosts.
    The offset resumes INSIDE a crowded cell; a partial page never asserts absence.
    Completed inventories need no rescan until the receiver changes cell.
    """
    validate_definition(definition, information_definition)
    if type(limit) is not int or not 1 <= limit <= 4096 or type(sector_budget) is not int or not 1 <= sector_budget <= 64:
        raise ValueError("Invalid historical radio query budget")
    anchor, sectors = local_domain(position, definition)
    key = (definition.rules_key, world.scope, anchor)
    cursor = cursor or {}
    cell, offset = (cursor.get("cell", 0), cursor.get("offset", 0)) if cursor.get("anchor") == key else (0, 0)
    if type(cell) is not int or not 0 <= cell <= len(sectors) or type(offset) is not int or offset < 0 or (cell == len(sectors) and offset):
        raise ValueError("Invalid historical radio cursor")
    result, count, examined = [], 0, 0
    session = manifest.new_session(world)
    while cell < len(sectors) and count < limit and examined < sector_budget:
        inventory = manifest._physical_inventory(session, (sectors[cell],))
        examined += 1
        if offset > len(inventory.sites):
            raise ValueError("Historical radio cursor outside physical inventory")
        while offset < len(inventory.sites) and count < limit:
            site = inventory.sites[offset]
            host = manifest.operative_id(world, site)
            history = query_host(world, definition, information_definition, host, session=session)
            if history and history.emissions:
                result.append(history)
            count += 1
            offset += 1
        if offset == len(inventory.sites):
            cell, offset = cell+1, 0
    return RadioPage(tuple(result), dict(anchor=key, cell=cell, offset=offset), cell == len(sectors), examined, count)


def resolve_emission(state, emission_id):
    """Common authored/procedural lookup, with no materialization or ledger write."""
    snapshot = state.world.narrative_snapshot
    emission = snapshot.get("radio_emissions", {}).get(emission_id)
    if emission:
        return snapshot["radio_emitters"][emission.emitter_id], emission
    world = state.world
    if world.radio_history_version != VERSION or not emission_id.startswith("@HR1:") or not emission_id.endswith(":0"):
        return None, None
    host = emission_id[5:-2]
    history = world.procedural_radio_search.get("histories", {}).get(host)
    if history is None:
        from retorno.worldgen.generator import universe_definition
        history = query_host(universe_definition(state), world.radio_definition,
            world.information_definition, host)
    if history:
        for emission in history.emissions:
            if emission.emission_id == emission_id:
                return history.emitter, emission
    return None, None


def validate_state(state):
    """Validate pinned rules and exact searched cache window, never knowledge."""
    world = state.world
    if world.radio_history_version == LEGACY_VERSION:
        if world.radio_definition is not None or world.procedural_radio_search:
            raise ValueError("Mixed historical/legacy radio / Radio histórica y legacy mezcladas")
        return
    if world.radio_history_version != VERSION:
        raise ValueError("Unsupported radio history / Historia de radio no admitida")
    validate_definition(world.radio_definition, world.information_definition, current=True)
    if world.radio_definition != define_radio(world.narrative_snapshot, world.information_definition):
        raise ValueError("Authored radio precedence changed / Precedencia de radio authored modificada")
    search = world.procedural_radio_search
    if not search:
        return
    normal = {"cursor", "histories", "reception_offset"}
    if set(search) not in (normal, normal | {"window_start", "window_remaining"}):
        raise ValueError("Invalid historical radio search state")
    from retorno.worldgen.generator import universe_definition
    physical = universe_definition(state)
    cursor = search["cursor"]
    key = cursor.get("anchor")
    if (not isinstance(key, tuple) or len(key) != 3 or key[:2] != (world.radio_definition.rules_key, physical.scope)
            or not isinstance(key[2], tuple) or len(key[2]) != 3 or any(type(v) is not int for v in key[2])):
        raise ValueError("Historical radio search belongs to another universe")
    # It is legitimate to save immediately after movement, before listening.
    position = tuple(v*10. for v in key[2])
    _, sectors = local_domain(position, world.radio_definition)
    cell, offset = cursor.get("cell"), cursor.get("offset")
    if (set(cursor) != {"anchor", "cell", "offset"} or type(cell) is not int or not 0 <= cell <= len(sectors)
            or type(offset) is not int or offset < 0 or (cell == len(sectors) and offset)):
        raise ValueError("Invalid historical radio search cursor")
    start = search.get("window_start", dict(anchor=key, cell=0, offset=0))
    if (not isinstance(start, dict) or set(start) != {"anchor", "cell", "offset"}
            or start["anchor"] != key or type(start["cell"]) is not int
            or type(start["offset"]) is not int or not 0 <= start["cell"] <= len(sectors)
            or start["offset"] < 0 or (start["cell"] == len(sectors) and start["offset"])
            or (start["cell"], start["offset"]) > (cell, offset)):
        raise ValueError("Invalid historical radio cache window")
    expected, session = {}, manifest.new_session(physical)
    for i in range(start["cell"], cell + bool(offset)):
        sites = manifest._physical_inventory(session, (sectors[i],)).sites
        lower = start["offset"] if i == start["cell"] else 0
        if lower > len(sites):
            raise ValueError("Historical radio cache window skips sites")
        if i == cell:
            if offset > len(sites):
                raise ValueError("Historical radio cursor skips sites")
            sites = sites[:offset]
        for site in sites[lower:]:
            host = manifest.operative_id(physical, site)
            history = query_host(physical, world.radio_definition, world.information_definition, host, session=session)
            if history and history.emissions:
                expected[host] = history
    if expected != search["histories"] or len(expected) > Balance.HISTORICAL_RADIO_LOCAL_HOST_LIMIT:
        raise ValueError("Historical radio local index mismatch / Índice local de radio histórica incompatible")
    receive_offset = search["reception_offset"]
    if type(receive_offset) is not int or not 0 <= receive_offset < max(1, len(expected)):
        raise ValueError("Invalid historical radio reception cursor")
    remaining = search.get("window_remaining")
    if remaining is not None and (type(remaining) is not int or not 0 <= remaining <= len(expected)):
        raise ValueError("Invalid historical radio window progress")
