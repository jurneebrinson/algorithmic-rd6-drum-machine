import mido

print("Available MIDI outputs:")
for name in mido.get_output_names():
    print("  ", name)