# 🎛️ Algorithmic RD-6 Drum Machine

A generative rhythm engine that algorithmically drives patterns sounded by the Behringer RD-6 drum machine. This project explores algorithmic music generation, MIDI sequencing, and real-time rhythm manipulation through Python.

It combines rule-based generative systems with live MIDI output to create evolving drum grooves that can be played, tested, and exported.

---

## ✨ Features

- 🧠 Algorithmic groove generation (rule-based + stochastic variation)
- 🥁 RD-6-inspired drum mapping (kick, snare, hats, accents)
- 🎚 Swing, timing drift, and groove humanization
- 🎹 MIDI output for DAW integration or external hardware
- 🔁 Loop-based pattern engine for real-time playback
- 🧪 Unit tests for MIDI logic and note mapping
- 📊 Experimental scripts for generative rhythm design

---

## 📁 Project Structure

algorithmic-rd6-drum-machine/

│

├── src/ # Core engine (generators + MIDI playback)

│ ├── rd6_rhythm_generator.py

│ ├── play_one_bar.py

│ ├── seamless_swing_loop.py

│ └── hear_swing.py

│

├── experiments/ # Prototyping & generative exploration

│ └── first_step_generator.py

│

├── tests/ # Unit tests for rhythm logic + MIDI

│ ├── test_rd6_midi.py

│ ├── test_note_map.py

│ └── test_available_ports.py

│
├── media/ # Demo assets (video + writeup)

│

├── saved_grooves/ # Generated patterns / exports

│

├── requirements.txt

└── .gitignore


---

## 🚀 Getting Started

### 1. Clone the repo

```bash
git clone https://github.com/jurneebrinson/algorithmic-rd6-drum-machine.git
cd algorithmic-rd6-drum-machine
```

### 2. Create virtual environment
```bash
python3 -m venv .venv
source .venv/bin/activate
```

## 3. Install dependencies
```bash
pip install -r requirements.txt
```
---

## 4. Running the System

### Play a single generated bar
```bash
python src/play_one_bar.py
```

### Run continuous swing loop
```bash
python src/seamless_swing_loop.py
```

### Listen to swing behavior
```bash
python src/hear_swing.py
```

### Run the algorithmic generator
```bash
python src/rd6_rhythm_generator
```

---

## Design Philosophy
This project treats rhythm as a computational system rather than fixed sequences. Instead of static drum patterns, it generates evolving grooves using:

- Rule-based probability systems
- Timing perturbation (swing + drift)
- Structured randomness
- MIDI event scheduling

The goal is to simulate intentional imperfection—a controlled balance between machine precision and human feel.

---

## Technical Stack
- Python 3.10+
- mido (MIDI handling)
- python-rtmidi (real-time output)
- NumPy (probability / timing logic)
- PyTest (testing framework)

---

## Media
- 🎥 Demo video: media/Algorithmic Drum Programming Video.mp4
- 📄 Project write-up: media/MUS 410 Final Project Write Up.pdf

---

## Author
Jurnee Brinson

University of Oregon

Focus: Music Production • Data Science • Creative Systems
