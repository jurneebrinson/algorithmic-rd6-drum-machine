# seamless_swing_loop.py
import time
import mido

# ---- Adjust to your setup ----
PORT_HINT   = "RHYTHM DESIGNER RD-6"
CHANNEL     = 0                 # RD-6 MIDI IN Channel 1 -> mido index 0
BPM         = 124.0
SWING       = 0.3             # 0.00 straight; ~0.20–0.35 = clear
BARS        = 8                # how many bars to play continuously
ALT_AB      = False             # True -> alternate bar: straight (A) vs swing (B)

# Common notes (tweak if your RD-6 mapping differs)
NOTE_CH = 42  # Closed Hat
NOTE_BD = 36  # Kick
NOTE_SD = 38  # Snare

def pick_port(hint: str) -> str:
    for name in mido.get_output_names():
        if hint.lower() in name.lower():
            return name
    raise RuntimeError(f"RD-6 port not found. Available: {mido.get_output_names()}")

def make_pattern(include_kick_snare=True):
    """Hats every 16th for maximum audibility of swing; optional BD/SD for context."""
    events = {s: [] for s in range(16)}
    for s in range(16):
        events[s].append((NOTE_CH, 100))
    if include_kick_snare:
        for s in (0, 4, 8, 12):  # 4-on-the-floor
            events[s].append((NOTE_BD, 112))
        for s in (4, 12):        # backbeats
            events[s].append((NOTE_SD, 104))
    return events

if __name__ == "__main__":
    port_name = pick_port(PORT_HINT)
    step_sec = (60.0 / BPM) / 4.0
    total_steps = 16 * BARS

    # Build your bar once; we'll reuse it
    bar = make_pattern(include_kick_snare=True)

    print(f"Using: {port_name} | BPM={BPM:.1f} | SWING={SWING:.2f} | BARS={BARS} | ALT_AB={ALT_AB}")
    with mido.open_output(port_name) as port:
        start = time.perf_counter()
        cumulative_delay = 0.0   # grows by swing*step_sec whenever we place a swung (odd) step
        for n in range(total_steps):
            bar_index  = n // 16
            step_in_bar = n % 16
            # If alternating, odd-numbered bars (1-based) are swung; even bars are straight
            bar_is_swung = (not ALT_AB) or ((bar_index % 2) == 1)

            # Decide if this step gets swing: odd step within the bar *and* bar is swung
            apply_swing = bar_is_swung and (step_in_bar % 2 == 1)

            # Compute target time using a continuous schedule
            if apply_swing:
                # We add swing to *this* step by increasing the cumulative_delay *before* we schedule it
                cumulative_delay += SWING * step_sec
            target = start + (n * step_sec) + cumulative_delay

            # Sleep until target
            now = time.perf_counter()
            if target > now:
                time.sleep(target - now)

            # Emit all events scheduled at this step (immediate note_off is fine for drums)
            for (note, vel) in bar.get(step_in_bar, []):
                port.send(mido.Message('note_on',  note=note, velocity=vel, channel=CHANNEL))
                port.send(mido.Message('note_off', note=note, velocity=0,  channel=CHANNEL))

    print("Done.")