# Step 1: Codify sound classes + rules + minimal generator + MIDI session loop
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Set, Optional
import random
import os
import time
import threading
import datetime as dt
import uuid

# --- Optional MIDI dependency (live + export) ---
try:
    import mido
    MIDO_AVAILABLE = True
except Exception:
    MIDO_AVAILABLE = False

# ----------------------------
# Types & core data structures
# ----------------------------
Rule      = Callable[['Context', 'Pattern', int, 'SoundClass'], bool]
SoftPref  = Callable[['Context', 'Pattern', int, 'SoundClass'], float]  # returns +/- probability adjustment
Pattern   = Dict[int, List[str]]  # pattern[step] -> list of sound names placed at that step

@dataclass
class SoundClass:
    name: str
    note: int
    channel: int
    base_probability: float
    allowed_steps: Set[int]
    hard_rules: List[Rule] = field(default_factory=list)
    soft_prefs: List[SoftPref] = field(default_factory=list)

@dataclass
class Context:
    steps: int = 16
    rng: random.Random = field(default_factory=lambda: random.Random(123))

# ----------------------------
# Utility: common step sets
# ----------------------------
ALL_STEPS = set(range(16))
DOWNBEATS = {0, 4, 8, 12}
BACKBEATS = {4, 12}
OFFBEATS  = {1, 3, 5, 7, 9, 11, 13, 15}

# ----------------------------
# Hard rules (must be True)
# ----------------------------
def rule_no_adjacent_open_hats(ctx: Context, pattern: Pattern, step: int, sc: SoundClass) -> bool:
    """For OpenHat: don't place at step if previous step already has OpenHat."""
    if sc.name != "OpenHat":
        return True
    prev = step - 1
    if prev >= 0 and "OpenHat" in pattern.get(prev, []):
        return False
    return True

def rule_no_consecutive_snares(ctx: Context, pattern: Pattern, step: int, sc: SoundClass) -> bool:
    """Block snare if the immediately previous step has a snare."""
    if sc.name != "Snare":
        return True
    prev = step - 1
    if prev >= 0 and "Snare" in pattern.get(prev, []):
        return False
    return True

def rule_no_oh_ch_overlap(ctx: Context, pattern: Pattern, step: int, sc: SoundClass) -> bool:
    """Prevent CH and OH from appearing at the same step (apply to both)."""
    if sc.name == "OpenHat" and "ClosedHat" in pattern.get(step, []):
        return False
    if sc.name == "ClosedHat" and "OpenHat" in pattern.get(step, []):
        return False
    return True

def rule_accent_must_follow_hit(ctx: Context, pattern: Pattern, step: int, sc: SoundClass) -> bool:
    """Accent only valid if some other sound is also placed at this step."""
    if sc.name != "Accent":
        return True
    return len([n for n in pattern.get(step, []) if n != "Accent"]) > 0

def rule_no_oh_cym_overlap(ctx: Context, pattern: Pattern, step: int, sc: SoundClass) -> bool:
    """Prevent Cymbal and OH from appearing at the same step (apply to both)."""
    if sc.name == "OpenHat" and "Cymbal" in pattern.get(step, []):
        return False
    if sc.name == "Cymbal" and "OpenHat" in pattern.get(step, []):
        return False
    return True

# ----------------------------
# Soft preferences (probability nudges)
# ----------------------------
def pref_kick_downbeats(ctx: Context, pattern: Pattern, step: int, sc: SoundClass) -> float:
    """Slightly increase kick probability on strong beats."""
    if sc.name != "Kick":
        return 0.0
    return 0.20 if step in DOWNBEATS else 0.0

def pref_hat_steady(ctx: Context, pattern: Pattern, step: int, sc: SoundClass) -> float:
    """Encourage closed hats to form a steady subdivision."""
    if sc.name != "ClosedHat":
        return 0.0
    # Gentle push everywhere, a bit more on offbeats for groove
    return 0.10 if (step % 2 == 0) else 0.15

def pref_avoid_tom_overlap(ctx: Context, pattern: Pattern, step: int, sc: SoundClass) -> float:
    """
    Penalize probability if the *other* tom is already at this step.
    Returns a negative nudge to discourage overlap (e.g., -0.35).
    """
    if sc.name not in ("LowTom", "HighTom"):
        return 0.0

    names = pattern.get(step, [])
    if sc.name == "LowTom" and "HighTom" in names:
        return -0.2
    if sc.name == "HighTom" and "LowTom" in names:
        return -0.2
    return 0.0

# ----------------------------
# Probability adjustment helper
# ----------------------------
def adjusted_probability(sc: SoundClass, step: int, ctx: Context, pattern: Pattern) -> float:
    p = sc.base_probability
    for pref in sc.soft_prefs:
        p += float(pref(ctx, pattern, step, sc))
    return max(0.0, min(1.0, p))

# ----------------------------
# Generator (core loop)
# ----------------------------
def generate_bar(sound_classes: List[SoundClass], ctx: Context) -> Pattern:
    pattern: Pattern = {s: [] for s in range(ctx.steps)}

    for step in range(ctx.steps):
        for sc in sound_classes:
            if step not in sc.allowed_steps:
                continue

            # hard rules
            ok = True
            for rule in sc.hard_rules:
                if not rule(ctx, pattern, step, sc):
                    ok = False
                    break
            if not ok:
                continue

            # probability
            p = adjusted_probability(sc, step, ctx, pattern)
            if ctx.rng.random() < p:
                pattern[step].append(sc.name)

    return pattern

# ----------------------------
# Pretty printing
# ----------------------------
def print_grid(pattern: Pattern, sound_order: List[str]):
    header = "Step | " + " ".join(f"{s:>2}" for s in range(16))
    print(header)
    print("-" * len(header))
    for name in sound_order:
        row = [name.ljust(6) + "|"]
        for s in range(16):
            cell = "██" if name in pattern.get(s, []) else " ."
            row.append(cell)
        print(" ".join(row))
    print()

# ============================
# === NEW: MIDI Utilities  ===
# ============================

### Config / mapping
MIDI_CHANNEL = 0 
ACCENT_BOOST = 20  # velocity boost if "Accent" present on a step
DEFAULT_VELOCITY = {
    "Kick": 105,
    "Snare": 100,
    "ClosedHat": 90,
    "OpenHat": 100,
    "Clap": 102,
    "LowTom": 96,
    "HighTom": 96,
    "Cymbal": 100,
}
TICKS_PER_BEAT = 480  # for MIDI file export

def ensure_dirs():
    os.makedirs("saved_grooves", exist_ok=True)

def bpm_to_midi_tempo(bpm: float) -> int:
    return int(60_000_000 / max(1, bpm))

def pick_port(hint: str) -> Optional[str]:
    """Pick a MIDI output port containing the hint substring (case-insensitive)."""
    if not MIDO_AVAILABLE:
        return None
    names = mido.get_output_names()
    for n in names:
        if hint.lower() in n.lower():
            return n
    return None

def pattern_step_accent(pattern: Pattern, step: int) -> bool:
    return "Accent" in pattern.get(step, [])

def iter_step_notes(pattern: Pattern, step: int, instrument_map: Dict[str, int]) -> List[int]:
    """Returns MIDI notes to trigger for this step (skips Accent as it's not a note)."""
    names = [n for n in pattern.get(step, []) if n != "Accent"]
    notes = []
    for name in names:
        if name in instrument_map:
            notes.append(instrument_map[name])
    return notes


def unique_midi_path(base_id: str, folder: str = "saved_grooves") -> str:
    """
    Returns a unique .mid path like:
        saved_grooves/rd6_YYYYmmdd_HHMMSS_seed_123456789__t173...__a1b2c3.mid
    Uses high-res timestamp + short UUID to guarantee uniqueness.
    """
    ensure_dirs()
    ts_ns = str(time.time_ns())
    token = uuid.uuid4().hex[:8]
    fname = f"{base_id}__t{ts_ns}__{token}.mid"
    return os.path.join(folder, fname)


# --- Live Playback Thread (continuous-time, cumulative swing) ---
def playback_loop(stop_evt,
                  pattern,                 # Dict[int, List[str]] step -> list of sound names
                  bpm: float,
                  instrument_map: Dict[str, int],
                  port_name: str,
                  swing: float = 0.0):
    """
    Continuous-time scheduler (matches your seamless_swing_loop.py approach):
      • One continuous clock from 'start' (no per-bar re-anchoring)
      • Cumulative swing applied *before* scheduling each swung (odd) step
      • Accent boosts velocity for all notes on that step
    """
    swing = max(0.0, min(0.5, float(swing)))
    step_sec = (60.0 / bpm) / 4.0            # duration of one 16th
    steps_per_bar = 16

    # Continuous timeline state
    start = time.perf_counter()
    cumulative_delay = 0.0                    # grows by swing*step_sec on each swung (odd) step
    n = 0                                     # continuous step index across bars

    # Optional ultra-tight landing (uncomment if you want sub-ms alignment)
    # SPIN_WINDOW = 0.001
    # def sleep_until(t_target: float):
    #     while True:
    #         now = time.perf_counter()
    #         remain = t_target - now
    #         if remain <= 0:
    #             break
    #         if remain > SPIN_WINDOW:
    #             time.sleep(remain - SPIN_WINDOW)
    #         # else: spin the final micro-slice

    with mido.open_output(port_name) as port:
        while not stop_evt.is_set():
            bar_index   = n // steps_per_bar
            step_in_bar = n % steps_per_bar

            # Swung if odd step AND swing>0 (you can add A/B alternation later if you like)
            apply_swing = (step_in_bar % 2 == 1) and (swing > 0.0)

            # Apply swing BEFORE computing the target time (key detail)
            if apply_swing:
                cumulative_delay += swing * step_sec

            # Schedule on the continuous timeline
            target = start + (n * step_sec) + cumulative_delay

            # Sleep until target (simple sleep is usually enough with this scheduler)
            remain = target - time.perf_counter()
            if remain > 0:
                time.sleep(remain)
            # If you enabled sleep_until above, replace the two lines with:
            # sleep_until(target)

            # Accent handling (velocity boost)
            boost = ACCENT_BOOST if pattern_step_accent(pattern, step_in_bar) else 0

            # Emit all notes for this step (skip "Accent" token)
            for name in pattern.get(step_in_bar, []):
                if name == "Accent":
                    continue
                note = instrument_map.get(name)
                if note is None:
                    continue
                base_vel = DEFAULT_VELOCITY.get(name, 96)
                vel = min(127, base_vel + boost)
                port.send(mido.Message('note_on',  note=note, velocity=vel, channel=MIDI_CHANNEL))
                port.send(mido.Message('note_off', note=note, velocity=0,  channel=MIDI_CHANNEL))

            n += 1

# --- MIDI File Export ---
def export_midi_file(pattern: Pattern,
                     filename: str,
                     bpm: float,
                     instrument_map: Dict[str, int]) -> str:
    if not MIDO_AVAILABLE:
        raise RuntimeError("mido is not installed. Install with: pip install mido")

    ensure_dirs()
    mf = mido.MidiFile(ticks_per_beat=TICKS_PER_BEAT)
    tr = mido.MidiTrack()
    mf.tracks.append(tr)

    tr.append(mido.MetaMessage("set_tempo", tempo=bpm_to_midi_tempo(bpm), time=0))
    tr.append(mido.MetaMessage("time_signature", numerator=4, denominator=4, clocks_per_click=24, notated_32nd_notes_per_beat=8, time=0))
    tr.append(mido.MetaMessage("track_name", name="RD-6 Pattern", time=0))

    ticks_per_step = TICKS_PER_BEAT // 4  # 16th
    for step in range(16):
        # write delta time
        delta = ticks_per_step if step > 0 else 0

        names = [n for n in pattern.get(step, []) if n != "Accent"]
        if not names:
            # advance time with no notes
            tr.append(mido.Message("note_on", channel=MIDI_CHANNEL, note=35, velocity=0, time=delta))  # dummy zero-vel
            continue

        # Accent as velocity boost
        boost = ACCENT_BOOST if pattern_step_accent(pattern, step) else 0
        first = True
        for name in names:
            note = instrument_map.get(name)
            if note is None:
                continue
            base_vel = DEFAULT_VELOCITY.get(name, 96)
            vel = min(127, base_vel + boost)
            tr.append(mido.Message("note_on", channel=MIDI_CHANNEL, note=note, velocity=vel, time=delta if first else 0))
            tr.append(mido.Message("note_off", channel=MIDI_CHANNEL, note=note, velocity=0, time=1))
            first = False

    mf.save(filename)
    return filename


def make_id(seed: int) -> str:
    # Python 3.11+ exposes dt.UTC; older versions use dt.timezone.utc
    try:
        utc = dt.UTC
    except AttributeError:
        utc = dt.timezone.utc
    ts = dt.datetime.now(utc).strftime("%Y%m%d_%H%M%S")
    return f"rd6_{ts}_seed_{seed}"

# ============================
# ===== Session Manager =====
# ============================

def session_loop(sound_classes: List[SoundClass],
                 instrument_map: Dict[str, int],
                 bpm: float,
                 port_hint: Optional[str] = None,
                 swing: float = 0.0,
                 save_midis: bool = True):
    """
    Generates a groove, loops it to the RD-6 until you:
      [s]ave -> write .mid and continue looping the SAME pattern
      [n]ext -> stop current loop and generate next pattern
      [q]uit -> stop and exit
    """
    ensure_dirs()

    # Try to open a MIDI port for live preview if possible
    port_name = None
    if MIDO_AVAILABLE and port_hint:
        port_name = pick_port(port_hint)
        if port_name:
            print(f"[MIDI] Using output port: {port_name}")
        else:
            print(f"[MIDI] Could not find port containing '{port_hint}'. Live preview will be disabled.")
    else:
        if not MIDO_AVAILABLE:
            print("[MIDI] mido not installed; live preview disabled.")
        else:
            print("[MIDI] No port hint given; live preview disabled.")

    print("\nControls: [s]ave [n]ext [q]uit")

    while True:
        # New seed per candidate for variety & reproducibility
        seed = random.randrange(1_000_000_000)
        ctx = Context(rng=random.Random(seed))
        pattern = generate_bar(sound_classes, ctx)

        # Print the grid for visual reference
        print_grid(pattern, [sc.name for sc in sound_classes])

        # Start live playback thread (if port available)
        stop_evt = threading.Event()
        player_thread = None
        if port_name:
            player_thread = threading.Thread(
                target=playback_loop,
                args=(stop_evt, pattern, bpm, instrument_map, port_name, swing),
                daemon=True
            )
            player_thread.start()
        print("[MIDI] Playing... (looping)")

        # --- Stay on this pattern until user asks for next/quit ---
        while True:
            action = input("[s]ave / [n]ext / [q]uit? ").strip().lower()

            if action == "s":
                # Save without stopping playback
                rid = make_id(seed)  # readable base id
                if save_midis:
                    out_path = unique_midi_path(rid)  # <-- always unique
                    try:
                        export_midi_file(pattern, out_path, bpm, instrument_map)
                        print(f"Saved MIDI: {out_path}")
                    except RuntimeError as e:
                        print(f"[WARN] {e}\n(MIDI export skipped.)")
                print("Saved. Continuing to loop this pattern. Press 'n' for next or 'q' to quit.")
                continue  # keep looping and re-prompt

            elif action == "n":
                # Stop playback and move to the next pattern
                if player_thread:
                    stop_evt.set()
                    player_thread.join(timeout=1.0)
                print("Generating next...\n")
                break  # break inner loop -> outer loop generates a new seed/pattern

            elif action == "q":
                # Stop playback and quit the session
                if player_thread:
                    stop_evt.set()
                    player_thread.join(timeout=1.0)
                print("Goodbye!")
                return  # exit the function entirely

            else:
                print("Unrecognized input. Use s/n/q. (Still looping current pattern.)")
                continue

def ask_bpm_and_swing(default_bpm: float = 120.0, default_swing: float = 0.0):
    """
    Prompt the user for BPM and swing only.
    Press Enter to accept defaults.
    Returns (bpm, swing).
    """

    print("\n======================================")
    print("   RD-6 Algorithmic Drum Generator")
    print("======================================")
    print("Before we start, choose your BPM and swing amount.")
    print("Press Enter to accept the defaults [denoted in brackets].\n")

    def ask_float(prompt: str, default: float, lo: float, hi: float) -> float:
        while True:
            raw = input(f"{prompt} [{default}]: ").strip()
            if raw == "":
                return default
            try:
                val = float(raw)
                if not (lo <= val <= hi):
                    print(f"Please enter a value between {lo} and {hi}.")
                    continue
                return val
            except ValueError:
                print("Please enter a number or press Enter for the default.")

    bpm = ask_float("BPM (between 30 and 300)", default_bpm, lo=30.0, hi=300.0)
    swing = ask_float("Swing (Between 0.0 and 0.5)", default_swing, lo=0.0, hi=0.5)
    return bpm, swing

# ----------------------------
# Example configuration and run
# ----------------------------
if __name__ == "__main__":
    # Confirmed RD-6 mapping
    INSTRUMENT_MAP = {
        "Kick":      36,
        "Snare":     40,
        "ClosedHat": 42,
        "OpenHat":   46,
        "Clap":      39,
        "LowTom":    45,
        "HighTom":   50,
        "Cymbal":    51,
        # "Accent":  (no note; handled as velocity boost)
    }

    # === Define sound classes ===
    kick = SoundClass(
        name="Kick",
        note=INSTRUMENT_MAP["Kick"],
        channel=MIDI_CHANNEL,
        base_probability=0.60,
        allowed_steps=DOWNBEATS,
        hard_rules=[],
        soft_prefs=[pref_kick_downbeats],
    )
    snare = SoundClass(
        name="Snare",
        note=INSTRUMENT_MAP["Snare"],
        channel=MIDI_CHANNEL,
        base_probability=0.90,
        allowed_steps=BACKBEATS,
        hard_rules=[rule_no_consecutive_snares],
        soft_prefs=[],
    )
    closed_hat = SoundClass(
        name="ClosedHat",
        note=INSTRUMENT_MAP["ClosedHat"],
        channel=MIDI_CHANNEL,
        base_probability=0.80,
        allowed_steps=ALL_STEPS,
        hard_rules=[rule_no_oh_ch_overlap],
        soft_prefs=[pref_hat_steady],
    )
    open_hat = SoundClass(
        name="OpenHat",
        note=INSTRUMENT_MAP["OpenHat"],
        channel=MIDI_CHANNEL,
        base_probability=0.30,
        allowed_steps=OFFBEATS,
        hard_rules=[rule_no_adjacent_open_hats, rule_no_oh_ch_overlap, rule_no_oh_cym_overlap],
        soft_prefs=[],
    )

    # Optional additional voices
    clap = SoundClass(
        name="Clap",
        note=INSTRUMENT_MAP["Clap"],
        channel=MIDI_CHANNEL,
        base_probability=0.30,
        allowed_steps=ALL_STEPS,
        hard_rules=[],     
        soft_prefs=[],
    )
    low_tom = SoundClass(
        name="LowTom",
        note=INSTRUMENT_MAP["LowTom"],
        channel=MIDI_CHANNEL,
        base_probability=0.20,
        allowed_steps=ALL_STEPS,
        hard_rules=[],
        soft_prefs=[pref_avoid_tom_overlap],
    )
    high_tom = SoundClass(
        name="HighTom",
        note=INSTRUMENT_MAP["HighTom"],
        channel=MIDI_CHANNEL,
        base_probability=0.18,
        allowed_steps=ALL_STEPS,
        hard_rules=[],
        soft_prefs=[pref_avoid_tom_overlap],
    )
    cymbal = SoundClass(
        name="Cymbal",
        note=INSTRUMENT_MAP["Cymbal"],
        channel=MIDI_CHANNEL,
        base_probability=0.04,
        allowed_steps=ALL_STEPS,
        hard_rules=[rule_no_oh_cym_overlap],
        soft_prefs=[],
    )
    accent = SoundClass(
        name="Accent",
        note=0,  # no actual note; symbolic
        channel=MIDI_CHANNEL,
        base_probability=0.15,
        allowed_steps=ALL_STEPS,
        hard_rules=[rule_accent_must_follow_hit],
        soft_prefs=[],
    )

    # Priority order matters; earlier classes "claim" steps before later ones
    sound_classes = [
        kick,
        snare,
        clap,
        closed_hat,
        open_hat,
        low_tom,
        high_tom,
        cymbal,
        accent,    # keep accent last so it observes what's already on the step
    ]

    # === Run the session loop ===
    PORT_HINT = "RD-6"  # try partials like "RHYTHM DESIGNER", "RD-6", or device name shown by mido
   
   #Ask the user only for BPM and Swing (Enter accepts defaults)
    BPM, SWING = ask_bpm_and_swing(default_bpm=120.0, default_swing=0.0)


    session_loop(
        sound_classes=sound_classes,
        instrument_map=INSTRUMENT_MAP,
        bpm=BPM,
        port_hint=PORT_HINT,   # set to None if you don't want live preview
        swing=0.0,             # try 0.1–0.2 for light swing
        save_midis=True,      # set False if you don't want to export files
    )
