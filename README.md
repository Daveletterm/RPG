# Mythic Bond RPG Prototype

This repository contains a self-contained, text-based slice of the Mythic Bond
creature-collecting RPG.  The core battle and exploration systems live in
`main.py`; assets such as prototype sprites are stored under `assets/`.

## Getting started

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

The prototype has no third-party dependencies, but using a virtual environment
keeps your Python installation tidy.

## Command-line controls

Running `python main.py` launches a small command-line interface:

* `NORTH`, `SOUTH`, `EAST`, `WEST` – move around the overworld
* `WHERE` – print your current coordinates and terrain
* `STATUS` – show your party
* `HISTORY` – list the most recent overworld messages
* `SAVE` / `LOAD` – write or restore the save file at `saves/savegame.json`
* `QUIT` – exit the prototype

During a battle you can use:

* `MOVES` – list available moves
* `ATTACK <n>` – use move number *n* (alias: `A <n>`)
* `STATUS` – show HP for both monsters
* `ENEMY` – inspect the opposing monster
* `LOG` – replay the battle log
* `RUN` – try to escape the encounter

## Repository notes

* Saved games are ignored by Git (see `.gitignore`).
* All logic is pure Python and suitable for reuse in other front-ends.
* The module exposes a `run_cli()` helper if you prefer to embed the prototype
  in another script.

Feel free to fork the project and experiment with new moves, monsters, or map
layouts!  Contributions that add polish or new content are very welcome.
