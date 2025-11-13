# Mythic Bond Prototype

This repository contains a small top-down RPG prototype built with
[Pygame](https://www.pygame.org/).  Roam a hand-crafted town rendered with
textured tiles, trigger wild encounters in tall grass, and battle creatures in a
simple turn-based system.

## Getting started

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows use: .venv\\Scripts\\activate
pip install -r requirements.txt
python main.py
```

The prototype opens a 640x480 window titled **Mythic Bond Prototype**.  A
scrolling camera follows your hero so the overworld can grow well beyond the
viewport. Use the arrow keys to walk around; step into grass tiles to find
battles.

## Controls

### Overworld

* **Arrow keys** – move the player (the camera pans to keep you in view)
* **Tab / P** – open the party menu overlay
* **S** – write your current location and party to `savegame.json`
* **Esc** – close the game window

Visit the light-green healing floor inside the small house to fully restore your
party. While in the party menu, use **Up/Down** to highlight a monster and read
its stats and moves. Tap **Left/Right** to switch between the active party and
your long-term storage. Press **Enter / Space** on a party slot to mark it for
reordering; move the highlight to a new position with **Up/Down** and press
**Enter / Space** again to swap the two monsters (press **Esc** to cancel).
Press **Tab** or **P** again to return to the overworld. You can inspect up to
six party slots at once; empty slots are shown so you can plan future captures.
Press **S** in this view to save without leaving the menu.

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

## Building the overworld

The explorable area lives in the `MAP_LAYOUT` constant inside `main.py`. Each
string represents a row of tiles and can be as wide as you like; add or remove
rows to grow the map vertically. The renderer automatically scrolls and clamps
to the new dimensions, so you can keep extending the story without touching the
camera code.

Tile legend (feel free to add your own by extending `TILE_TYPES`):

| Symbol | Meaning             | Walkable? |
| ------ | ------------------- | --------- |
| `.`    | Cobblestone path    | ✅        |
| `G`    | Tall grass (battles)| ✅        |
| `#`    | Stone wall / cliff  | ❌        |
| `S`    | Building wall       | ❌        |
| `D`    | Doorway             | ✅        |
| `H`    | Healing floor       | ✅        |
| `C`    | Great hall flooring | ❌        |
| `W`    | Water               | ❌        |
| `B`    | Wooden bridge       | ✅        |

Tiles are rendered with small procedural patterns, so grass looks lush, paths
feature pebbles, and water shimmers. Update the color or pattern settings in
`TILE_TYPES` to experiment with new scenery.

Add new monsters by placing their sprite(s) in `assets/sprites/` and appending a
JSON entry to `assets/monsters.json`. Reference front/back sprites by filename
under the `sprites.front` and optional `sprites.back` keys. Each monster lists
the moves it can use; the move names must already exist in
`create_move_library()` inside `main.py`.
Feel free to fork the project and extend the content, add audio/visual polish, or
experiment with new battle mechanics.
