"""C2b installed data checks; structural evidence, not a public journey."""
from copy import deepcopy
import json
import math
from pathlib import Path
import pickle
import shutil
from tempfile import TemporaryDirectory
from unittest.mock import patch

from retorno.bootstrap import create_initial_state_prologue
from retorno.core.engine import Engine
from retorno.core import lore
from retorno.io.save_load import save_single_slot, load_single_slot, SaveLoadError
from retorno.model.os import Locale
from retorno.runtime import data_loader as data
from lore_relative_placement_integration import DRAFT, PRIMARY, PREFIX, public_view


def path_in_view(nodes, start, target):
    queue = [(start, [start])]
    seen = {start}
    for current, path in queue:
        if current == target:
            return path
        for other in sorted(nodes[current].links) if current in nodes else ():
            if other in nodes and other not in seen:
                seen.add(other)
                queue.append((other, path + [other]))
    return None  # Only the finite inspected graph, never a global negative proof.


def main():
    installed = data._DATA_ROOT / "arcs/amanecer_elena_01.json"
    assert installed.read_bytes() == (DRAFT / "amanecer_elena_01.draft.json").read_bytes()
    assert [a["arc_id"] for a in data.load_arcs()] == ["amanecer_elena_01"]
    assert len(data.load_singles()) == 5 and len(data.load_locations()) == 5
    texts = list((DRAFT / "textos").glob("*.txt"))
    assert len(texts) == 10
    for text in texts:
        assert text.read_bytes() == (data._DATA_ROOT / "lore/packs/amanecer_elena_01" / text.name).read_bytes()
    evidence = []
    for seed in (701, 1, 29):
        for locale in ((Locale.EN, Locale.ES) if seed == 701 else (Locale.EN,)):
            s = create_initial_state_prologue(seed=seed)
            s.os.locale = locale
            snap = s.world.narrative_snapshot
            host = snap["reservations"][PRIMARY]["node_id"]
            assert host not in s.world.known_nodes and "LIRIA" not in s.world.known_nodes
            frozen = pickle.dumps(s)
            visible = public_view(s)
            assert pickle.dumps(s) == frozen
            twin = deepcopy(s)
            twin.world.narrative_snapshot = {}
            assert public_view(twin) == visible
            entries = {e["piece_key"]: e for e in lore._iter_all_pieces(s)}
            frozen = pickle.dumps(s)
            candidates, nodes = lore._historical_candidates(s, entries[PRIMARY])
            assert pickle.dumps(s) == frozen and candidates == [host]
            host_path = path_in_view(nodes, "ECHO_7", host)
            liria_path = path_in_view(nodes, "ECHO_7", "LIRIA")
            for path in (host_path, liria_path):
                if path:
                    for left, right in zip(path, path[1:]):
                        assert math.dist((nodes[left].x_ly,nodes[left].y_ly,nodes[left].z_ly),
                                         (nodes[right].x_ly,nodes[right].y_ly,nodes[right].z_ly)) <= 45
            Engine().tick(s, 1)
            assert public_view(s).find("LIRIA") == -1
            assert s.world.lore_placements.piece_to_node[PRIMARY] == host
            keys = [k for k in entries if k.startswith(PREFIX) and k != PRIMARY]
            assert len(keys) == 4
            assert all(s.world.lore_placements.piece_to_node[k] == "LIRIA" for k in keys)
            assert lore.piece_constraints_ok(entries[PRIMARY]["piece"], lore.build_lore_context(s, host))
            paths = []
            for key in [PRIMARY] + keys:
                node_id = s.world.lore_placements.piece_to_node[key]
                path = entries[key]["piece"]["path_template"].format(lang=locale.value)
                files = s.world.node_pools[node_id].injected_files
                assert len([f for f in files if f["path"] == path]) == 1
                assert next(f for f in files if f["path"] == path)["content"].strip()
                paths.append((node_id, path))
            with TemporaryDirectory(prefix="retorno-c2b-save-") as directory:
                slot = Path(directory) / "installed.dat"
                save_single_slot(s, slot)
                restored = load_single_slot(slot).state
                assert restored.world.narrative_snapshot == snap
                assert restored.world.lore_placements == s.world.lore_placements
                lore.run_lore_scheduler_tick(restored)
                for node_id, path in paths:
                    assert len([f for f in restored.world.node_pools[node_id].injected_files if f["path"] == path]) == 1
            evidence.append(dict(seed=seed, locale=locale.value, host=host,
                                 host_path_in_certified_view=host_path,
                                 liria_path_in_certified_view=liria_path,
                                 liria=snap["positions"]["LIRIA"]))
    assert len({row["host"] for row in evidence}) > 1
    with TemporaryDirectory(prefix="retorno-c2b-old-catalog-") as directory:
        old_root = Path(directory) / "data"
        shutil.copytree(data._DATA_ROOT, old_root)
        (old_root / "arcs/amanecer_elena_01.json").unlink()
        slot = Path(directory) / "old.dat"
        with patch.object(data, "_DATA_ROOT", old_root):
            save_single_slot(create_initial_state_prologue(seed=701), slot)
        previous = slot.read_bytes()
        try:
            load_single_slot(slot)
        except SaveLoadError as exc:
            assert "catalog" in str(exc)
        else:
            raise AssertionError("old catalogue save silently reinterpreted")
        assert slot.read_bytes() == previous
    Path("/tmp/retorno-c2b-productive-evidence.json").write_text(json.dumps(evidence, indent=2))
    print("AMANECER PRODUCTIVE DATA PASSED; public journey assessed separately")


if __name__ == "__main__":
    main()
