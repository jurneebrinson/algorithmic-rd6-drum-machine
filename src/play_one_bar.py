# play_one_bar.py
import time, mido

PORT_HINT = "RHYTHM DESIGNER RD-6"
CHANNEL = 0
BPM = 124.0
SWING = 0.0 # 0.0 for straight

# Fill with your confirmed notes
INSTRUMENT_MAP = {"BD":36, "SD":40, "CH":42, "OH":46}

def pick_port(hint):
    for name in mido.get_output_names():
        if hint.lower() in name.lower():
            return name
    raise RuntimeError("RD-6 port not found.")

def play_bar(events_by_step: dict[int, list[tuple[int,int]]], bpm=BPM, swing=SWING):
    step_sec = (60.0 / bpm) / 4.0  # 16th notes
    t0 = time.perf_counter()
    with mido.open_output(pick_port(PORT_HINT)) as port:
        for step in range(16):
            swing_delay = swing * step_sec if (step % 2 == 1) else 0.0
            target = t0 + step * step_sec + swing_delay
            now = time.perf_counter()
            if target > now:
                time.sleep(target - now)
            for note, vel in events_by_step.get(step, []):
                port.send(mido.Message('note_on', note=note, velocity=vel, channel=CHANNEL))
                port.send(mido.Message('note_off', note=note, velocity=0, channel=CHANNEL))

if __name__ == "__main__":
    BD, SD, CH, OH = INSTRUMENT_MAP["BD"], INSTRUMENT_MAP["SD"], INSTRUMENT_MAP["CH"], INSTRUMENT_MAP["OH"]
    events = {}
    for s in (0, 4, 8, 12): events.setdefault(s, []).append((BD, 112))
    for s in (4, 12):        events.setdefault(s, []).append((SD, 104))
    for s in (2, 6, 10, 14): events.setdefault(s, []).append((CH, 96))

    print(f"Playing one bar at {BPM} BPM (swing {SWING})…")
    play_bar(events)