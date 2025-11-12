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
* **Esc** – close the game window

Visit the light-green healing floor inside the small house to fully restore your
party.

### Battle

* **Arrow keys / W S** – pick menu options
* **Enter / Space / Z** – confirm selections
* **Esc** – back out of sub-menus

Choose **Fight** to select a move, **Bag** (placeholder) to do nothing, **Party**
to swap monsters (placeholder), or **Run** to attempt an escape.

## Project structure

* `main.py` – full game logic and rendering loop
* `assets/` – placeholder directory for future sprites or audio
* `requirements.txt` – dependency pin for Pygame
* `.gitignore` – ignores virtual environments, caches, and save data

Feel free to fork the project and extend the content, add audio/visual polish, or
experiment with new battle mechanics.
