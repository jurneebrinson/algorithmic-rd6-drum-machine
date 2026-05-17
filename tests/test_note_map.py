# test_note_map.py
import time, mido

PORT_HINT = "RHYTHM DESIGNER RD-6"
CHANNEL = 0  # RD-6 MIDI IN Channel 1
VELOCITY = 110

# Drum sound mappings according to the RD-6 manual:
CANDIDATES = [
    ("BD", 36),
    ("SD", 40),
    ("LT", 45),
    ("HT", 50),
    ("CP", 39),
    ("CY", 51),
    ("OH", 46),
    ("CH", 42)
]

def pick_port(hint):
    for name in mido.get_output_names():
        if hint.lower() in name.lower():
            return name
    raise RuntimeError("RD-6 port not found.")

if __name__ == "__main__":
    port_name = pick_port(PORT_HINT)
    print("Using:", port_name)
    with mido.open_output(port_name) as port:
        for name, note in CANDIDATES:
            print(f"-> {name} (note {note})")
            port.send(mido.Message('note_on', note=note, velocity=VELOCITY, channel=CHANNEL))
            time.sleep(0.05)
            port.send(mido.Message('note_off', note=note, velocity=0, channel=CHANNEL))
            time.sleep(1.0)  # gap to hear clearly