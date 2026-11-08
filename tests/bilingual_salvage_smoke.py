"""P5c: bilingual assignment and real salvage jobs, without navigation journeys."""
from contextlib import redirect_stdout
from copy import deepcopy
import io
import json
from pathlib import Path
import pickle
from tempfile import TemporaryDirectory

from retorno.bootstrap import create_initial_state_prologue
from retorno.cli import repl
from retorno.core import lore
from retorno.io.save_load import save_single_slot, load_single_slot
from retorno.model.os import Locale, normalize_path
from lore_relative_placement_integration import salvage, PREFIX, PRIMARY
from lore_channel_preference_and_unlock_smoke import main as channel_regression


def quiet(fn, *args):
    with redirect_stdout(io.StringIO()) as stream:
        fn(*args)
    return stream.getvalue()


def test_recovery(start):
    s = create_initial_state_prologue(seed=1)
    repl.apply_config_value(s.os, "lang", start)
    lore.run_lore_scheduler_tick(s)
    reservations = deepcopy(s.world.narrative_snapshot["reservations"])
    placements = deepcopy(s.world.lore_placements.piece_to_node)
    entries = {e["piece_key"]: e for e in lore._iter_all_pieces(s) if e["piece_key"].startswith(PREFIX)}
    secondary = [key for key in entries if key != PRIMARY]
    host = reservations[PRIMARY]["node_id"]
    assert len(secondary) == 4
    assert all(placements[key] == "LIRIA" for key in secondary)
    for key, entry in entries.items():
        node_id = placements[key]
        for lang in ("en", "es"):
            path = entry["piece"]["path_template"].format(lang=lang)
            matching = [f for f in s.world.node_pools[node_id].injected_files if f["path"] == path]
            assert len(matching) == 1
            assert matching[0]["content"] == lore._content_from_ref(entry["piece"]["content_ref_" + lang], s)
            assert not any(f["path"] == path for nid, pool in s.world.node_pools.items()
                           if nid != node_id for f in pool.base_files + pool.injected_files)
    assert not any("/data/amanecer/" in path for path in s.os.fs)

    # Existing service fixture relocates only the test ship and exercises real
    # drone jobs. This verifies delivery, not the already-certified P3 journey.
    salvage(s, host)
    assert "LIRIA" not in s.world.known_nodes
    primary = entries[PRIMARY]["piece"]
    for lang in (start, "es" if start == "en" else "en"):
        repl.apply_config_value(s.os, "lang", lang)
        path = "/remote/" + host + primary["path_template"].format(lang=lang)
        assert path in s.os.fs
        assert "LINK:" in quiet(repl.render_cat, s, path)
        assert "LIRIA" in s.world.known_links["HARBOR_12"]
    assert s.world.arc_placements["amanecer_elena_01"]["discovered"] == {"liria_navigation_index"}
    salvage(s, "LIRIA")
    paths = ["/remote/LIRIA" + entries[key]["piece"]["path_template"].format(lang=lang)
             for key in secondary for lang in ("en", "es")]
    assert len(paths) == 8 and all(path in s.os.fs for path in paths)
    for lang in (start, "es" if start == "en" else "en"):
        repl.apply_config_value(s.os, "lang", lang)
        for key in secondary:
            piece = entries[key]["piece"]
            path = "/remote/LIRIA" + piece["path_template"].format(lang=lang)
            expected = lore._content_from_ref(piece["content_ref_" + lang], s)
            assert s.os.fs[path].content == expected and expected in quiet(repl.render_cat, s, path)
    assert set(entries) <= s.world.lore.delivered
    assert len([key for key in s.world.lore.delivered if key.startswith(PREFIX)]) == 5
    assert len(s.world.arc_placements["amanecer_elena_01"]["secondary"]) == 4
    progress = deepcopy((s.world.lore.delivered, s.world.arc_placements,
                         s.world.node_pools["LIRIA"].delivered_piece_ids))
    fs, links = deepcopy(s.os.fs), deepcopy(s.world.known_links)
    salvage(s, "LIRIA")
    assert s.os.fs == fs and s.world.known_links == links
    assert (s.world.lore.delivered, s.world.arc_placements,
            s.world.node_pools["LIRIA"].delivered_piece_ids) == progress
    assert s.world.lore_placements.piece_to_node == placements
    assert s.world.narrative_snapshot["reservations"] == reservations
    with TemporaryDirectory() as folder:
        slot = Path(folder) / "bilingual.dat"
        save_single_slot(s, slot)
        loaded = load_single_slot(slot).state
        assert loaded.os.fs == fs and loaded.world.known_links == links
        assert loaded.world.lore.delivered == s.world.lore.delivered
        assert loaded.world.arc_placements == s.world.arc_placements
        assert loaded.world.lore_placements == s.world.lore_placements
        assert loaded.world.narrative_snapshot["reservations"] == reservations
        for path in paths:
            assert loaded.os.fs[path].content in quiet(repl.render_cat, loaded, path)
        salvage(loaded, "LIRIA")
        assert loaded.os.fs == fs
        assert (loaded.world.lore.delivered, loaded.world.arc_placements,
                loaded.world.node_pools["LIRIA"].delivered_piece_ids) == progress
    return dict(start=start, host=host, documents=4, variants=8, logical_deliveries=5,
                repeat_salvage="unchanged", persistence=True)


def fixture():
    s = create_initial_state_prologue(seed=1)
    lore.initialize_node_pool(s, "ECHO_7")
    entry = dict(piece_key="single:bilingual_atomic", piece_id="bilingual_atomic", arc_id="",
                 role="single", channels=["salvage_data"],
                 piece=dict(path_template="/data/atomic.{lang}.txt",
                            content_ref_en="lore/packs/amanecer_elena_01/elena_01_escotilla_h3.en.txt",
                            content_ref_es="lore/packs/amanecer_elena_01/elena_01_escotilla_h3.es.txt"))
    return s, entry


def test_atomic_and_legacy():
    base, entry = fixture()
    for locale in (Locale.EN, Locale.ES):
        for collision in ("en", "es"):
            for family in ("base_files", "injected_files"):
                s = deepcopy(base)
                s.os.locale = locale
                getattr(s.world.node_pools["ECHO_7"], family).append(
                    dict(path=f"/data//atomic.{collision}.txt", content="occupied"))
                before = pickle.dumps(s)
                assert not lore._assign_piece_to_node(s, entry, "ECHO_7")
                assert pickle.dumps(s) == before  # No half-assignment or bookkeeping.
    s = deepcopy(base)
    assert lore._assign_piece_to_node(s, entry, "ECHO_7")
    frozen = pickle.dumps(s)
    assert not lore._assign_piece_to_node(s, entry, "ECHO_7")
    assert pickle.dumps(s) == frozen
    for mode in ("monolingual", "shared_path", "inline"):
        for lang in ("en", "es"):
            s, piece = deepcopy(base), deepcopy(entry)
            s.os.locale = Locale(lang)
            if mode == "monolingual":
                piece["piece"].pop("content_ref_es")
            elif mode == "shared_path":
                piece["piece"]["path_template"] = "/data/shared.txt"
            else:
                piece["piece"] = dict(path_template="/data/inline.{lang}.txt", line="retained inline record")
            expected = lore._file_for_salvage_piece(piece, lang, s)
            assert lore._assign_piece_to_node(s, piece, "ECHO_7")
            files = s.world.node_pools["ECHO_7"].injected_files
            assert files == [expected]
            assert normalize_path(files[0]["path"]).startswith("/data/")


def main():
    evidence = [test_recovery(lang) for lang in ("en", "es")]
    print("PASS EN->ES and ES->EN: primary + four Elena documents, real salvage/read, single identities, repeat, save/load")
    test_atomic_and_legacy()
    print("PASS atomic EN/ES collisions in base/injected files, repeat assignment, monolingual/shared-path/inline compatibility")
    channel_regression()
    Path("/tmp/retorno-p5c-evidence.json").write_text(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
