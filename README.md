# Mythic Bond Prototype

This repository contains a small top-down RPG prototype built with
[Pygame](https://www.pygame.org/).  Move around a handcrafted map, trigger wild
encounters in tall grass, and battle creatures in a simple turn-based system.

## Getting started

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows use: .venv\\Scripts\\activate
pip install -r requirements.txt
python main.py
```

The prototype opens a 640x480 window titled **Mythic Bond Prototype**.  Use the
arrow keys to walk around; step into grass tiles to find battles.

## Controls

### Overworld

* **Arrow keys** – move the player
* **Tab / P** – open the party menu overlay
* **S** – write your current location and party to `savegame.json`
* **Esc** – close the game window

Visit the light-green healing floor inside the small house to fully restore your
party. While in the party menu, use **Up/Down** to highlight a monster and read
its stats and moves. Tap **Left/Right** to switch between the active party and
your long-term storage. Press **Tab** or **P** again to return to the overworld.
You can inspect up to six party slots at once; empty slots are shown so you can
plan future captures. Press **S** in this view to save without leaving the menu.

### Battle

* **Arrow keys / W S** – pick menu options
* **Enter / Space / Z** – confirm selections
* **Esc** – back out of the move list

Choose **Fight** to select a move, **Switch** to tag in another party member
(costs a turn), **Catch** to try recruiting the foe, or **Run** to attempt an
escape. The currently selected party leader takes part in combat. Catch chances
improve as the wild monster's HP drops. Captured monsters join your party
automatically when a slot is free; if your party is full they are safely routed
to storage.

## Saving and continuing

The game automatically looks for `savegame.json` next to `main.py` when it
starts. If present, the file restores your previous location, party (up to six
monsters), and any additional monsters you've stored. Use the **S** shortcut
from the overworld or party menu to update the save file at any time.

## Project structure

* `main.py` – full game logic, rendering loop, and menu handling
* `assets/monsters.json` – roster and stat definitions for every creature
* `assets/sprites/` – drop front/back PNG sprites here (referenced by name in
  `monsters.json`)
* `requirements.txt` – dependency pin for Pygame
* `.gitignore` – ignores virtual environments, caches, and save data

Add new monsters by placing their sprite(s) in `assets/sprites/` and appending a
JSON entry to `assets/monsters.json`. Reference front/back sprites by filename
under the `sprites.front` and optional `sprites.back` keys. Each monster lists
the moves it can use; the move names must already exist in
`create_move_library()` inside `main.py`.
Feel free to fork the project and extend the content, add audio/visual polish, or
experiment with new battle mechanics.
