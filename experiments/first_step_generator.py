# 01_first_step_generator.py
# Step 1: Codify sound classes + rules + minimal generator (prints a 16-step grid)
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Set
import random

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
    # you can add bpm, swing, bar_index later as needed

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
    """For OpenHat: don't place at step if previous step already has OpenHat.
    (Forward-looking adjacency will be handled when we reach the next step.)"""
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
    return len(pattern.get(step, [])) > 0

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

# ----------------------------
# Probability adjustment helper
# ----------------------------
def adjusted_probability(sc: SoundClass, step: int, ctx: Context, pattern: Pattern) -> float:
    p = sc.base_probability
    # apply soft prefs as linear nudges, then clamp
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
    # build per-sound rows
    for name in sound_order:
        row = [name.ljust(6) + "|"]
        for s in range(16):
            cell = "██" if name in pattern.get(s, []) else " ."
            row.append(cell)
        print(" ".join(row))

# ----------------------------
# Example configuration and run
# ----------------------------
if __name__ == "__main__":
    # Replace these with your confirmed RD-6 mapping later
    INSTRUMENT_MAP = {
        "Kick":      36,
        "Snare":     38,
        "ClosedHat": 42,
        "OpenHat":   46,
        "Accent":    56,  # placeholder; your RD-6 may not use a distinct note for accent
    }

    ctx = Context(rng=random.Random(2026))  # reproducible seed

    # Define sound classes per your conceptual defaults
    kick = SoundClass(
        name="Kick",
        note=INSTRUMENT_MAP["Kick"],
        channel=0,
        base_probability=0.60,
        allowed_steps=DOWNBEATS,
        hard_rules=[],
        soft_prefs=[pref_kick_downbeats],
    )
    snare = SoundClass(
        name="Snare",
        note=INSTRUMENT_MAP["Snare"],
        channel=0,
        base_probability=0.90,
        allowed_steps=BACKBEATS,
        hard_rules=[rule_no_consecutive_snares],
        soft_prefs=[],
    )
    closed_hat = SoundClass(
        name="ClosedHat",
        note=INSTRUMENT_MAP["ClosedHat"],
        channel=0,
        base_probability=0.80,
        allowed_steps=ALL_STEPS,
        hard_rules=[rule_no_oh_ch_overlap],
        soft_prefs=[pref_hat_steady],
    )
    open_hat = SoundClass(
        name="OpenHat",
        note=INSTRUMENT_MAP["OpenHat"],
        channel=0,
        base_probability=0.20,
        allowed_steps=OFFBEATS,
        hard_rules=[rule_no_adjacent_open_hats, rule_no_oh_ch_overlap],
        soft_prefs=[],
    )
    # Accent is optional; leave out until you define your accent workflow
    # accent = SoundClass(
    #     name="Accent",
    #     note=INSTRUMENT_MAP["Accent"],
    #     channel=0,
    #     base_probability=0.10,
    #     allowed_steps=ALL_STEPS,
    #     hard_rules=[rule_accent_must_follow_hit],
    #     soft_prefs=[],
    # )

    sound_classes = [kick, snare, closed_hat, open_hat]  # priority order matters

    pat = generate_bar(sound_classes, ctx)
    print_grid(pat, [sc.name for sc in sound_classes])

    # --- OPTIONAL: audition immediately on the RD-6 (simple player; no swing) ---
    TRY_AUDIO = False
    if TRY_AUDIO:
        import time, mido
        PORT_HINT = "RHYTHM DESIGNER RD-6"
        BPM = 124.0

        def pick_port(hint: str) -> str:
            for name in mido.get_output_names():
                if hint.lower() in name.lower():
                    return name
            raise RuntimeError(f"Could not find port containing {hint!r}. Found: {mido.get_output_names()}")

        port_name = pick_port(PORT_HINT)
        step_sec = (60.0 / BPM) / 4.0
        with mido.open_output(port_name) as port:
            t0 = time.perf_counter()
            for step in range(16):
                target = t0 + step * step_sec
                now = time.perf_counter()
                if target > now:
                    time.sleep(target - now)
                for name in pat[step]:
                    sc = next(s for s in sound_classes if s.name == name)
                    port.send(mido.Message('note_on', note=sc.note, velocity=100, channel=sc.channel))
                    port.send(mido.Message('note_off', note=sc.note, velocity=0, channel=sc.channel))