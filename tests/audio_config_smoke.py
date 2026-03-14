from __future__ import annotations

from retorno.audio.config import load_audio_config


def main() -> None:
    config = load_audio_config()

    assert config.version == 1
    assert config.ambient_cue_id == "ship_hum"
    assert config.startup_cue_id == "intro_booting"
    assert "ship_hum" in config.cues
    assert "intro_booting" in config.cues

    ambient = config.cues["ship_hum"]
    assert ambient.mode == "loop"
    assert ambient.channel == "ambient"
    assert ambient.path.name == "hum_loop_short.wav"
    assert ambient.path.exists()
    assert ambient.sample_count is not None and ambient.sample_count > 0
    assert ambient.fade_in_s > 0.0
    assert ambient.fade_out_s == 0.0
    assert ambient.loop_crossfade_s > 0.0

    startup = config.cues["intro_booting"]
    assert startup.mode == "once"
    assert startup.channel == "startup"
    assert startup.path.name == "intro_booting.ogg"
    assert startup.path.exists()
    assert startup.duration_s is not None and startup.duration_s > 0.0

    print("AUDIO CONFIG SMOKE PASSED")


if __name__ == "__main__":
    main()
