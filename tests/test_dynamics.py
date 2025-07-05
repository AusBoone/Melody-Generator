import sys
import types


def test_humanize_events_ranges():
    """``humanize_events`` should jitter time and velocity within bounds."""
    stub_mido = types.ModuleType("mido")
    stub_mido.Message = lambda *a, **k: None
    stub_mido.MidiFile = object
    stub_mido.MidiTrack = list
    stub_mido.MetaMessage = lambda *a, **k: None
    stub_mido.bpm2tempo = lambda bpm: bpm
    sys.modules.setdefault("mido", stub_mido)

    from melody_generator.dynamics import humanize_events

    class Msg:
        def __init__(self, time=0, velocity=64):
            self.time = time
            self.velocity = velocity

    msgs = [Msg(time=10, velocity=60), Msg(time=0, velocity=80), Msg(time=5)]
    humanize_events(msgs)
    assert 0 <= msgs[0].time <= 25
    assert 50 <= msgs[0].velocity <= 70
    assert msgs[1].time == 0
    assert 70 <= msgs[1].velocity <= 90
    assert msgs[2].time >= 0
    sys.modules.pop("mido", None)
