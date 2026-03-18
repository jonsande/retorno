from __future__ import annotations

from retorno.audio.config import load_audio_config


def main() -> None:
    config = load_audio_config()

    assert config.version == 1
    assert config.ambient_cue_id == "ship_hum"
    assert config.startup_new_game_cue_id == "intro_booting"
    assert config.startup_load_game_cue_id == "intro_loading"
    assert "ship_hum" in config.cues
    assert "intro_booting" in config.cues
    assert "intro_loading" in config.cues
    assert "alert_critical" in config.cues
    assert "signal_detected" in config.cues
    assert "dock_start" in config.cues
    assert "dock_complete" in config.cues
    assert config.event_routes["job_completed"].cue_id == "job_done"
    assert config.event_routes["signal_detected"].cue_id == "signal_detected"
    assert config.event_routes["boot_blocked"].cue_id == "error"
    assert config.event_routes["job_queued:dock"].cue_id == "dock_start"
    assert config.event_routes["docked"].cue_id == "dock_complete"
    assert config.default_event_route is not None
    assert config.default_event_route.cue_id == "alert_ping"
    assert config.warnings == ()
    assert config.music.default_volume == 0.60
    assert config.music.ambient_ducking_gain == 0.82
    assert config.music.tracks
    assert config.event_routes["power_net_deficit"].cue_id == "alert_ping"
    assert config.event_routes["power_bus_instability:critical"].cue_id == "alert_critical"
    assert config.event_routes["low_power_quality:critical"].cue_id == "alert_critical"
    assert config.event_routes["drone_bay_maintenance_blocked"].cue_id == "alert_ping"

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
    assert startup.volume == 0.75

    load_startup = config.cues["intro_loading"]
    assert load_startup.mode == "once"
    assert load_startup.channel == "startup"
    assert load_startup.path.exists()

    first_track = config.music.tracks[0]
    assert first_track.path.parent.name == "music"
    assert first_track.path.exists()
    assert first_track.track_id
    assert first_track.title

    print("AUDIO CONFIG SMOKE PASSED")


if __name__ == "__main__":
    main()
