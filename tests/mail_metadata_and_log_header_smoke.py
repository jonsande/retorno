from __future__ import annotations

import io
from contextlib import redirect_stdout

from retorno.bootstrap import create_initial_state_sandbox
from retorno.cli import repl
from retorno.core.lore import _deliver_piece, _file_for_salvage_piece, build_lore_context


def main() -> None:
    state = create_initial_state_sandbox()
    ctx = build_lore_context(state, state.world.current_node_id)

    piece_mail = {
        "id": "mail_meta_smoke",
        "mail_from": "Transit Liaison",
        "mail_subject": "Corridor attachment",
        "content_ref_en": "lore/singles/echo_fragment_01.en.txt",
        "content_ref_es": "lore/singles/echo_fragment_01.es.txt",
    }
    result = _deliver_piece(
        state,
        "smoke_arc",
        "mail_meta_smoke",
        piece_mail,
        "ship_os_mail",
        ctx,
        is_primary=False,
    )
    assert result.events, "Expected mail delivery event"

    out = io.StringIO()
    with redirect_stdout(out):
        repl.render_mailbox(state, "inbox")
    txt = out.getvalue()
    assert "from=Transit Liaison" in txt, f"Expected sender in inbox render: {txt}"
    assert "subj=Corridor attachment" in txt, f"Expected subject in inbox render: {txt}"

    piece_log = {
        "path_template": "/logs/records/mail_meta_smoke.{lang}.txt",
        "content_ref_en": "lore/singles/echo_fragment_01.en.txt",
        "content_ref_es": "lore/singles/echo_fragment_01.es.txt",
        "log_header": "SMOKE LOG // attachment",
    }
    entry = _file_for_salvage_piece({"piece_key": "single:mail_meta_smoke", "piece": piece_log}, "en")
    assert entry is not None, "Expected salvage_data file entry"
    content = str(entry.get("content", ""))
    assert content.startswith("SMOKE LOG // attachment"), "Expected log_header prepended in /logs file"

    print("MAIL METADATA + LOG HEADER SMOKE PASSED")


if __name__ == "__main__":
    main()
