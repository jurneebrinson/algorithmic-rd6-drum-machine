# test_rd6_midi.py
import time
import sys
import mido

# === Adjust these if needed ===
RD6_HINT = "RD-6"        # substring to find your RD-6 output port
TEST_NOTE = 36           # try 36 (Kick) or 38 (Snare) depending on your RD-6 mapping
CHANNEL = 0              # mido uses 0-based; 9 == MIDI channel 10 (drum channel)
VELOCITY = 110           # velocity/accent; tweak if your RD-6 responds to velocity

def pick_output(hint: str | None = None) -> str:
    outputs = mido.get_output_names()
    if not outputs:
        raise RuntimeError("No MIDI output ports found. Is the RD-6 connected and powered?")
    if hint:
        for name in outputs:
            if hint.lower() in name.lower():
                return name
    # If hint wasn't found, print the list and let the user pick the first one
    print("Available MIDI outputs:")
    for i, name in enumerate(outputs):
        print(f"  {i}: {name}")
    print("\nNo output matched the hint. Using the first port. "
          "Edit RD6_HINT or pass a different port name.")
    return outputs[0]

def send_test_hit(port_name: str, note: int, channel: int, velocity: int):
    print(f"Opening MIDI out: {port_name}")
    with mido.open_output(port_name) as port:
        # Send a short percussive hit
        msg_on = mido.Message('note_on', note=note, velocity=velocity, channel=channel)
        msg_off = mido.Message('note_off', note=note, velocity=0, channel=channel)
        port.send(msg_on)
        time.sleep(0.02)  # short duration; percussion doesn't need long sustains
        port.send(msg_off)
    print("Sent note_on/note_off successfully.")

if __name__ == "__main__":
    try:
        port = pick_output(RD6_HINT)
        print(f"Using: {port}")
        print(f"Sending test note {TEST_NOTE} on channel {CHANNEL+1} (midi channel {CHANNEL})...")
        send_test_hit(port, TEST_NOTE, CHANNEL, VELOCITY)
        print("If you didn't hear anything, try a different TEST_NOTE (e.g., 38), "
              "check the channel, or verify RD-6 MIDI settings.")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)