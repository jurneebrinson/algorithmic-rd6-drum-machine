import time
import mido

# ---- Configure these to match your system ----
PORT_HINT = "RHYTHM DESIGNER RD-6"  # substring that identifies your RD-6 port
CHANNEL = 0                         # RD-6 MIDI IN Channel 1 => mido channel index 0
BPM = 120.0
SWING = 0.30                        # 0.00 = straight; try 0.20–0.35 for clear swing
BARS = 16                            # how many bars to play
ALT_AB = False                      # if True: alternate straight (A) and swung (B) bars

# Common GM-ish drum notes (adjust if needed for your RD-6)
NOTE_CH = 42   # Closed Hat
NOTE_BD = 36   # Kick (optional, for context)
NOTE_SD = 40   # Snare (optional, for context)

def pick_port(hint: str) -> str:
    for name in mido.get_output_names():
        if hint.lower() in name.lower():
            return name
    raise RuntimeError(f"Could not find an output containing '{hint}'. Available: {mido.get_output_names()}")

def play_bar(port, events_by_step, bpm: float, swing: float, channel: int):
    """Play one 16-step bar with given bpm and swing."""
    step_sec = (60.0 / bpm) / 4.0  # 16th-note duration
    t0 = time.perf_counter()
    for step in range(16):
        # Delay odd 16ths by swing * step_sec (classic shuffle)
        swing_delay = (swing * step_sec) if (step % 2 == 1) else 0.0
        target_time = t0 + step * step_sec + swing_delay
        now = time.perf_counter()
        if target_time > now:
            time.sleep(target_time - now)

        for note, vel in events_by_step.get(step, []):
            port.send(mido.Message('note_on', note=note, velocity=vel, channel=channel))
            port.send(mido.Message('note_off', note=note, velocity=0, channel=channel))

def make_clear_swing_pattern(include_kick_snare: bool = True):
    """Hats on every 16th (best for hearing swing). Optional 4-on-the-floor + backbeats."""
    events = {s: [] for s in range(16)}
    # Hats every 16th
    for s in range(16):
        events[s].append((NOTE_CH, 100))
    # Optional: add kick/snare for context
    if include_kick_snare:
        for s in (0, 4, 8, 12):   # 4-on-the-floor
            events[s].append((NOTE_BD, 112))
        for s in (4, 12):         # backbeats
            events[s].append((NOTE_SD, 104))
    return events

if __name__ == "__main__":
    port_name = pick_port(PORT_HINT)
    print(f"Using MIDI out: {port_name}")
    print(f"BPM={BPM:.1f} | swing={SWING:.2f} | bars={BARS} | channel={CHANNEL+1}")

    pattern = make_clear_swing_pattern(include_kick_snare=True)

    with mido.open_output(port_name) as port:
        for bar_index in range(BARS):
            if ALT_AB and (bar_index % 2 == 0):
                # A: straight bar for reference
                print(f"Bar {bar_index+1}/{BARS}: straight")
                play_bar(port, pattern, bpm=BPM, swing=0.0, channel=CHANNEL)
            else:
                # B: swung bar
                print(f"Bar {bar_index+1}/{BARS}: swung ({SWING:.2f})")
                play_bar(port, pattern, bpm=BPM, swing=SWING, channel=CHANNEL)

    print("Done.")
