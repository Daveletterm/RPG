# Install pygame with: pip install pygame
# Run the game with: python main.py

import json
import math
import random
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set

import pygame


# ----------------------------------------------------------------------------
# Data definitions for moves and monsters
# ----------------------------------------------------------------------------


@dataclass
class Move:
    name: str
    power: int
    accuracy: float  # value between 0.0 and 1.0
    type: str


@dataclass
class Monster:
    name: str
    level: int
    max_hp: int
    current_hp: int
    attack: int
    defense: int
    speed: int
    type: str
    moves: List[Move] = field(default_factory=list)
    exp: int = 0
    exp_to_next: int = 20
    front_sprite: Optional[pygame.Surface] = field(default=None, repr=False)
    back_sprite: Optional[pygame.Surface] = field(default=None, repr=False)

    def is_fainted(self) -> bool:
        return self.current_hp <= 0

    def heal(self) -> None:
        self.current_hp = self.max_hp

    def gain_experience(self, amount: int) -> List[str]:
        """Add experience and return messages for any level ups."""
        messages: List[str] = []
        self.exp += amount
        while self.exp >= self.exp_to_next:
            self.exp -= self.exp_to_next
            self.level += 1
            # Simple stat growth for prototype level ups
            self.max_hp += 3
            self.attack += 2
            self.defense += 2
            self.speed += 1
            self.current_hp = self.max_hp
            self.exp_to_next = max(20, int(self.exp_to_next * 1.3))
            messages.append(f"{self.name} grew to level {self.level}!")
        return messages


# ----------------------------------------------------------------------------
# Monster templates and helper functions for creating parties
# ----------------------------------------------------------------------------


ASSETS_DIR = Path(__file__).parent / "assets"
SPRITE_DIR = ASSETS_DIR / "sprites"
MONSTER_DATA_FILE = ASSETS_DIR / "monsters.json"
TRAINER_DATA_FILE = ASSETS_DIR / "trainers.json"
SAVE_FILE = Path(__file__).parent / "savegame.json"

MAX_PARTY_SIZE = 6


def create_move_library() -> Dict[str, Move]:
    """Return the core move definitions. Extend this to add new moves."""
    return {
        "Cinder Snap": Move("Cinder Snap", power=18, accuracy=0.95, type="fire"),
        "Leaf Gust": Move("Leaf Gust", power=16, accuracy=0.9, type="grass"),
        "Ripple Shot": Move("Ripple Shot", power=20, accuracy=0.85, type="water"),
        "Nuzzle": Move("Nuzzle", power=10, accuracy=1.0, type="normal"),
        "Glacier Spit": Move("Glacier Spit", power=22, accuracy=0.85, type="ice"),
        "Aerial Rake": Move("Aerial Rake", power=19, accuracy=0.9, type="flying"),
        "Shadow Swipe": Move("Shadow Swipe", power=17, accuracy=0.95, type="dark"),
        "Night Pounce": Move("Night Pounce", power=14, accuracy=1.0, type="dark"),
    }


def load_sprite_image(filename: Optional[str]) -> Optional[pygame.Surface]:
    if not filename:
        return None
    sprite_path = Path(filename)
    if not sprite_path.is_absolute():
        sprite_path = SPRITE_DIR / sprite_path
    if not sprite_path.exists():
        return None
    try:
        image = pygame.image.load(str(sprite_path)).convert_alpha()
    except pygame.error:
        return None
    return pygame.transform.smoothscale(image, (96, 96))


def create_monster_templates(move_library: Dict[str, Move]) -> Dict[str, Monster]:
    """Load monster templates from JSON, falling back to built-in defaults."""

    if not MONSTER_DATA_FILE.exists():
        raise FileNotFoundError(
            "Missing monsters.json. Add your monster roster to assets/monsters.json."
        )

    with MONSTER_DATA_FILE.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    templates: Dict[str, Monster] = {}
    for entry in data.get("monsters", []):
        name = entry["name"]
        move_names = entry.get("moves", [])
        moves: List[Move] = []
        for move_name in move_names:
            if move_name not in move_library:
                raise ValueError(f"Move '{move_name}' referenced by {name} is not defined.")
            moves.append(move_library[move_name])

        sprites = entry.get("sprites", {})
        templates[name] = Monster(
            name=name,
            level=entry.get("level", 1),
            max_hp=entry.get("max_hp", 20),
            current_hp=entry.get("current_hp", entry.get("max_hp", 20)),
            attack=entry.get("attack", 10),
            defense=entry.get("defense", 10),
            speed=entry.get("speed", 10),
            type=entry.get("type", "normal"),
            moves=moves,
            exp=entry.get("exp", 0),
            exp_to_next=entry.get("exp_to_next", 20),
            front_sprite=load_sprite_image(sprites.get("front")),
            back_sprite=load_sprite_image(sprites.get("back")),
        )

    return templates


def load_monster_definitions() -> tuple[Dict[str, Move], Dict[str, Monster]]:
    """Load all monster-related data from disk and return (moves, templates)."""

    move_library = create_move_library()
    monster_templates = create_monster_templates(move_library)
    return move_library, monster_templates


def load_trainers() -> Dict[str, Dict[str, object]]:
    """Load trainer definitions from JSON into a dictionary keyed by id."""

    if not TRAINER_DATA_FILE.exists():
        return {}

    try:
        trainer_data = json.loads(TRAINER_DATA_FILE.read_text())
    except json.JSONDecodeError:
        return {}

    trainers: Dict[str, Dict[str, object]] = {}
    for entry in trainer_data.get("trainers", []):
        identifier = entry.get("id")
        name = entry.get("name")
        if not identifier or not name:
            continue
        trainers[str(identifier)] = {
            "id": str(identifier),
            "name": str(name),
            "is_gym_leader": bool(entry.get("is_gym_leader", False)),
            "badge_name": entry.get("badge_name"),
            "dialogue_before": entry.get("dialogue_before", []),
            "dialogue_after": entry.get("dialogue_after", []),
            "team": entry.get("team", []),
        }
    return trainers


def clone_monster(template: Monster) -> Monster:
    """Create a copy of a monster template so encounters do not share state."""
    return Monster(
        name=template.name,
        level=template.level,
        max_hp=template.max_hp,
        current_hp=template.current_hp,
        attack=template.attack,
        defense=template.defense,
        speed=template.speed,
        type=template.type,
        moves=list(template.moves),
        exp=template.exp,
        exp_to_next=template.exp_to_next,
        front_sprite=template.front_sprite,
        back_sprite=template.back_sprite,
    )


def monster_to_dict(monster: Monster) -> Dict[str, int | str]:
    return {
        "name": monster.name,
        "level": monster.level,
        "max_hp": monster.max_hp,
        "current_hp": monster.current_hp,
        "attack": monster.attack,
        "defense": monster.defense,
        "speed": monster.speed,
        "exp": monster.exp,
        "exp_to_next": monster.exp_to_next,
    }


def monster_from_dict(data: Dict[str, object], templates: Dict[str, Monster]) -> Optional[Monster]:
    name = data.get("name")
    if not name or name not in templates:
        return None
    base = clone_monster(templates[name])
    base.level = data.get("level", base.level)
    base.max_hp = data.get("max_hp", base.max_hp)
    base.current_hp = min(data.get("current_hp", base.max_hp), base.max_hp)
    base.attack = data.get("attack", base.attack)
    base.defense = data.get("defense", base.defense)
    base.speed = data.get("speed", base.speed)
    base.exp = data.get("exp", base.exp)
    base.exp_to_next = data.get("exp_to_next", base.exp_to_next)
    return base


def clamp_player_position(x: int, y: int) -> tuple[int, int]:
    return max(0, min(MAP_WIDTH - 1, x)), max(0, min(MAP_HEIGHT - 1, y))


def save_game_state(
    path: Path,
    player: "Player",
    party: List[Monster],
    storage: List[Monster],
    badges: Optional[List[str]] = None,
    defeated_trainers: Optional[List[str]] = None,
) -> None:
    """Persist the player's position, party, storage, and trainer progress."""

    badges = badges or []
    defeated_trainers = defeated_trainers or []
    data = {
        "player": {"x": player.tile_x, "y": player.tile_y},
        "party": [monster_to_dict(monster) for monster in party[:MAX_PARTY_SIZE]],
        "storage": [monster_to_dict(monster) for monster in storage],
        "badges": list(badges),
        "defeated_trainers": list(defeated_trainers),
    }
    path.write_text(json.dumps(data, indent=2))


def load_game_state(
    path: Path,
    templates: Dict[str, Monster],
    default_party: List[Monster],
    default_position: tuple[int, int],
) -> tuple[tuple[int, int], List[Monster], List[Monster], List[str], List[str]]:
    if not path.exists():
        return default_position, list(default_party), [], [], []

    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError:
        return default_position, list(default_party), [], [], []

    player_data = data.get("player", {})
    player_x = int(player_data.get("x", default_position[0]))
    player_y = int(player_data.get("y", default_position[1]))
    player_position = clamp_player_position(player_x, player_y)

    loaded_party: List[Monster] = []
    for entry in data.get("party", [])[:MAX_PARTY_SIZE]:
        monster = monster_from_dict(entry, templates)
        if monster:
            loaded_party.append(monster)

    if not loaded_party:
        loaded_party = list(default_party)

    loaded_storage: List[Monster] = []
    for entry in data.get("storage", []):
        monster = monster_from_dict(entry, templates)
        if monster:
            loaded_storage.append(monster)

    badges = data.get("badges", []) or []
    defeated_trainers = data.get("defeated_trainers", []) or []

    return player_position, loaded_party, loaded_storage, badges, defeated_trainers


# ----------------------------------------------------------------------------
# Overworld definitions: map data, tiles, and player movement helpers
# ----------------------------------------------------------------------------

TILE_SIZE = 32
WINDOW_WIDTH, WINDOW_HEIGHT = 640, 480
MAP_LAYOUT = [
    "############################################",
    "#.........GGGGGGGGGGGGGGGGGGGGGG...........#",
    "#...WWW...GGGGGGGGGGGGGGGGGGGGGG...........#",
    "#...WWW...GGGGGGGGGGGGGGGGGGGGGG...........#",
    "#...WWW...GGGGGGGGGGGGGGGGGGGGGG...........#",
    "#...WWW...GGGGGGGGGGGGGGGGGGGGGG...........#",
    "#...WWW..SSSSS..........SSSSS.WWWWWW.......#",
    "#...WWW..SSDSS..........SSDSS.WWWWWW.......#",
    "#.......................SSDSS.WWWWWW.......#",
    "#.............................WWWWWW.......#",
    "#..........................................#",
    "#...WBBBW...#.................#............#",
    "#...WWW.....#.GGGG...H...GGGG.#............#",
    "#...WWW.....#.GGGG...H...GGGG.#............#",
    "#...WWW.....#...T.........L...#............#",
    "#..........................................#",
    "#...WWWW..SSSSSS..........SSSSSSS..........#",
    "#...WWWW..SSSDSS..........SSSDSSS..........#",
    "#...WWWW...................................#",
    "#...WWWW...................................#",
    "#...WWWW.......GGGGGGGGGGGGGGGGGGGGGGG.....#",
    "#...WWWW.......GGGGG..H..GGGGGGGGGGGGG.....#",
    "#...WWWW.......GGGGG....GGGGGGGGGGGGGG.....#",
    "#..............GGGGG....GGGGGGGGGGGGGG.....#",
    "#..............GGGGGGGGGGGGGGGGGGGGGGG.....#",
    "#..........................................#",
    "#..........................................#",
    "############################################",
]
MAP_WIDTH = len(MAP_LAYOUT[0])
MAP_HEIGHT = len(MAP_LAYOUT)
MAP_PIXEL_WIDTH = MAP_WIDTH * TILE_SIZE
MAP_PIXEL_HEIGHT = MAP_HEIGHT * TILE_SIZE
DEFAULT_START_POSITION = (2, 2)
TRAINER_TILES = {"T": "forest_bug_catcher_1", "L": "grove_gym_leader"}

TILE_TYPES = {
    "#": {
        "walkable": False,
        "name": "Stone Wall",
        "pattern": "stone",
        "base_color": (76, 84, 104),
        "accent_color": (52, 58, 76),
    },
    ".": {
        "walkable": True,
        "name": "Cobblestone Path",
        "pattern": "path",
        "base_color": (196, 178, 128),
        "accent_color": (160, 140, 96),
    },
    "G": {
        "walkable": True,
        "name": "Tall Grass",
        "pattern": "grass",
        "base_color": (84, 156, 78),
        "accent_colors": [(70, 132, 66), (102, 176, 108), (60, 114, 62)],
    },
    "C": {
        "walkable": False,
        "name": "Great Hall",
        "pattern": "floor",
        "base_color": (168, 166, 192),
        "accent_color": (142, 140, 170),
    },
    "D": {
        "walkable": True,
        "name": "Doorway",
        "pattern": "door",
        "base_color": (196, 162, 108),
        "accent_color": (120, 88, 52),
    },
    "S": {
        "walkable": False,
        "name": "House Wall",
        "pattern": "house_wall",
        "base_color": (190, 186, 170),
        "accent_color": (124, 98, 68),
    },
    "H": {
        "walkable": True,
        "name": "Healing Floor",
        "pattern": "healing",
        "base_color": (170, 226, 208),
        "accent_color": (106, 176, 168),
    },
    "W": {
        "walkable": False,
        "name": "Water",
        "pattern": "water",
        "base_color": (42, 102, 168),
        "accent_color": (90, 164, 220),
    },
    "B": {
        "walkable": True,
        "name": "Bridge",
        "pattern": "planks",
        "base_color": (170, 138, 92),
        "accent_color": (118, 88, 54),
    },
    "T": {
        "walkable": True,
        "name": "Trainer Spot",
        "pattern": "path",
        "base_color": (212, 188, 140),
        "accent_color": (136, 118, 82),
    },
    "L": {
        "walkable": True,
        "name": "Leader Arena",
        "pattern": "path",
        "base_color": (200, 210, 160),
        "accent_color": (150, 160, 118),
    },
}


def create_patterned_tile_surface(
    tile_key: str, tile_info: Dict[str, object], tile_size: int
) -> pygame.Surface:
    """Build a textured tile surface for the overworld."""

    surface = pygame.Surface((tile_size, tile_size), pygame.SRCALPHA)
    base_color = tile_info.get("base_color", (200, 200, 200))
    surface.fill(base_color)  # type: ignore[arg-type]

    pattern = tile_info.get("pattern", "solid")
    rng = random.Random(f"{tile_key}-{tile_size}")

    def scatter_pixels(colors: List[tuple[int, int, int]], count: int) -> None:
        for _ in range(count):
            x = rng.randrange(tile_size)
            y = rng.randrange(tile_size)
            surface.set_at((x, y), colors[rng.randrange(len(colors))])

    if pattern == "grass":
        accent_colors = tile_info.get("accent_colors", []) or [
            (64, 132, 68),
            (100, 180, 110),
        ]
        scatter_pixels(accent_colors, tile_size * 3)
        for _ in range(tile_size // 2):
            start_x = rng.randrange(tile_size)
            start_y = rng.randrange(tile_size // 2, tile_size)
            end_x = start_x + rng.randint(-2, 2)
            end_y = start_y - rng.randint(3, 6)
            pygame.draw.line(
                surface,
                accent_colors[rng.randrange(len(accent_colors))],
                (start_x, start_y),
                (end_x, max(0, end_y)),
                1,
            )
    elif pattern == "path":
        accent = tile_info.get("accent_color", (140, 120, 80))
        scatter_pixels([accent, (220, 204, 160)], tile_size * 2)
        for _ in range(tile_size // 2):
            radius = rng.randint(1, 2)
            pygame.draw.circle(
                surface,
                (160, 150, 120),
                (rng.randrange(tile_size), rng.randrange(tile_size)),
                radius,
            )
    elif pattern == "stone":
        mortar = tile_info.get("accent_color", (60, 66, 84))
        brick_h = max(4, tile_size // 4)
        brick_w = max(6, tile_size // 3)
        for y in range(0, tile_size, brick_h):
            offset = (y // brick_h % 2) * (brick_w // 2)
            pygame.draw.line(surface, mortar, (0, y), (tile_size, y), 1)
            for x in range(-offset, tile_size, brick_w):
                rect = pygame.Rect(x, y, brick_w, brick_h)
                pygame.draw.rect(surface, mortar, rect, 1)
    elif pattern == "floor":
        accent = tile_info.get("accent_color", (148, 146, 170))
        block = max(4, tile_size // 4)
        for y in range(0, tile_size, block):
            for x in range(0, tile_size, block):
                if (x // block + y // block) % 2 == 0:
                    pygame.draw.rect(
                        surface,
                        accent,
                        pygame.Rect(x, y, block, block),
                    )
    elif pattern == "door":
        accent = tile_info.get("accent_color", (116, 88, 52))
        pygame.draw.rect(
            surface,
            accent,
            pygame.Rect(tile_size // 4, tile_size // 6, tile_size // 2, tile_size - tile_size // 3),
            0,
        )
        pygame.draw.circle(
            surface,
            (240, 220, 180),
            (tile_size // 2 + tile_size // 5, tile_size // 2),
            max(1, tile_size // 16),
        )
    elif pattern == "house_wall":
        beam = tile_info.get("accent_color", (120, 94, 68))
        pygame.draw.rect(surface, beam, pygame.Rect(0, 0, tile_size, max(2, tile_size // 16)))
        pygame.draw.rect(
            surface, beam, pygame.Rect(0, tile_size - max(2, tile_size // 16), tile_size, tile_size // 16)
        )
        pygame.draw.rect(surface, beam, pygame.Rect(tile_size // 3, 0, tile_size // 8, tile_size))
        pygame.draw.rect(
            surface, beam, pygame.Rect(tile_size - tile_size // 3, 0, tile_size // 8, tile_size)
        )
    elif pattern == "healing":
        accent = tile_info.get("accent_color", (90, 170, 160))
        cross_w = max(4, tile_size // 5)
        pygame.draw.rect(
            surface,
            accent,
            pygame.Rect(tile_size // 2 - cross_w // 2, tile_size // 4, cross_w, tile_size // 2),
        )
        pygame.draw.rect(
            surface,
            accent,
            pygame.Rect(tile_size // 4, tile_size // 2 - cross_w // 2, tile_size // 2, cross_w),
        )
    elif pattern == "water":
        accent = tile_info.get("accent_color", (86, 158, 220))
        for y in range(tile_size):
            blend = y / max(1, tile_size - 1)
            color = (
                int(base_color[0] * (1 - blend) + accent[0] * blend),
                int(base_color[1] * (1 - blend) + accent[1] * blend),
                int(base_color[2] * (1 - blend) + accent[2] * blend),
            )
            pygame.draw.line(surface, color, (0, y), (tile_size, y))
        wave_color = (230, 245, 255)
        for _ in range(tile_size // 2):
            start_x = rng.randrange(tile_size)
            length = rng.randint(tile_size // 2, tile_size)
            pygame.draw.arc(
                surface,
                wave_color,
                pygame.Rect(start_x - length // 2, rng.randrange(tile_size), length, tile_size // 2),
                0,
                math.pi,
                1,
            )
    elif pattern == "planks":
        accent = tile_info.get("accent_color", (110, 84, 60))
        plank_h = max(4, tile_size // 5)
        for y in range(0, tile_size, plank_h):
            pygame.draw.rect(surface, accent, pygame.Rect(0, y, tile_size, plank_h), 1)
            nail_y = y + plank_h // 2
            pygame.draw.circle(surface, (70, 50, 30), (tile_size // 4, nail_y), max(1, plank_h // 6))
            pygame.draw.circle(
                surface, (70, 50, 30), (tile_size - tile_size // 4, nail_y), max(1, plank_h // 6)
            )
    else:
        scatter_pixels([tuple(int(c * 0.9) for c in base_color)], tile_size)

    border = pygame.Surface((tile_size, tile_size), pygame.SRCALPHA)
    pygame.draw.rect(border, (0, 0, 0, 30), border.get_rect(), 1)
    surface.blit(border, (0, 0))

    return surface.convert_alpha()


def build_tile_surfaces(tile_types: Dict[str, Dict[str, object]], tile_size: int) -> Dict[str, pygame.Surface]:
    return {
        tile: create_patterned_tile_surface(tile, info, tile_size)
        for tile, info in tile_types.items()
    }


def create_player_sprite(tile_size: int) -> pygame.Surface:
    """Create a simple hero sprite with a distinct silhouette."""

    width = tile_size - 10
    height = tile_size - 4
    sprite = pygame.Surface((width, height), pygame.SRCALPHA)

    # Shadow
    pygame.draw.ellipse(
        sprite,
        (40, 40, 40, 120),
        pygame.Rect(width // 6, height - height // 6, width * 2 // 3, height // 5),
    )

    body_color = (210, 70, 70)
    highlight = (240, 110, 110)
    belt_color = (60, 60, 80)
    head_color = (238, 214, 190)

    body_rect = pygame.Rect(width // 3, height // 4, width // 3, height // 2)
    pygame.draw.rect(sprite, body_color, body_rect)
    pygame.draw.rect(sprite, highlight, body_rect.inflate(-width // 6, -height // 6))
    pygame.draw.rect(
        sprite,
        belt_color,
        pygame.Rect(body_rect.x, body_rect.y + body_rect.height // 2, body_rect.width, max(2, height // 12)),
    )

    head_radius = width // 4
    pygame.draw.circle(sprite, head_color, (width // 2, height // 4), head_radius)
    pygame.draw.circle(sprite, (50, 50, 50), (width // 2 - head_radius // 2, height // 4), max(1, head_radius // 5))
    pygame.draw.circle(sprite, (50, 50, 50), (width // 2 + head_radius // 2, height // 4), max(1, head_radius // 5))

    arm_color = (200, 180, 160)
    arm_width = max(2, width // 6)
    pygame.draw.rect(
        sprite,
        arm_color,
        pygame.Rect(body_rect.x - arm_width, body_rect.y + height // 8, arm_width, body_rect.height - height // 8),
    )
    pygame.draw.rect(
        sprite,
        arm_color,
        pygame.Rect(
            body_rect.right,
            body_rect.y + height // 8,
            arm_width,
            body_rect.height - height // 8,
        ),
    )

    return sprite.convert_alpha()


class Player:
    def __init__(self, tile_x: int, tile_y: int):
        self.tile_x = tile_x
        self.tile_y = tile_y

    def rect(self) -> pygame.Rect:
        return pygame.Rect(self.tile_x * TILE_SIZE, self.tile_y * TILE_SIZE, TILE_SIZE, TILE_SIZE)


# ----------------------------------------------------------------------------
# Battle system helpers
# ----------------------------------------------------------------------------


class BattleState:
    def __init__(
        self,
        player_party: List[Monster],
        enemy_monster: Monster,
        max_party_size: int,
        trainer: Optional[Dict[str, object]] = None,
        enemy_party: Optional[List[Monster]] = None,
    ):
        if not player_party:
            raise ValueError("Player party cannot be empty when a battle begins.")
        if all(monster.is_fainted() for monster in player_party):
            raise ValueError("All party monsters have fainted and cannot battle.")

        self.player_party = player_party
        self.trainer_info = trainer
        self.trainer_id = (trainer or {}).get("id")
        self.enemy_party = enemy_party or [enemy_monster]
        self.enemy_active_index = 0
        self.enemy_monster = self.enemy_party[self.enemy_active_index]
        self.max_party_size = max_party_size

        preferred_lead = 0
        if self.player_party[preferred_lead].is_fainted():
            preferred_lead = next(
                (
                    idx
                    for idx, monster in enumerate(self.player_party)
                    if not monster.is_fainted()
                ),
                0,
            )

        self.active_index = preferred_lead
        self.player_monster = self.player_party[self.active_index]
        self.switch_index = self.active_index
        self.force_switch = False

        self.menu_state = "action"  # "action", "move", or "switch"
        self.action_index = 0
        self.move_index = 0
        self.message_queue: List[Dict[str, Optional[Callable[[], None]]]] = []
        self.pending_enemy_turn = False
        self.after_battle_callback: Optional[Callable[[], None]] = None
        self.ended = False
        if self.trainer_info:
            self.action_options: List[str] = ["Fight", "Switch", "Run"]
        else:
            self.action_options = ["Fight", "Switch", "Catch", "Run"]
        self.captured_monster: Optional[Monster] = None
        self.captured_to_storage = False
        self.trainer_defeated = False
        self.badge_earned: Optional[str] = None

    @property
    def party_size(self) -> int:
        return len(self.player_party)

    def available_switch_targets(self) -> List[int]:
        return [
            idx
            for idx, monster in enumerate(self.player_party)
            if idx != self.active_index and not monster.is_fainted()
        ]

    def set_active_monster(self, index: int) -> None:
        self.active_index = index
        self.player_monster = self.player_party[index]
        self.switch_index = index

    def set_enemy_monster(self, index: int) -> None:
        self.enemy_active_index = index
        self.enemy_monster = self.enemy_party[index]

    def next_enemy_index(self) -> Optional[int]:
        for idx, monster in enumerate(self.enemy_party):
            if idx <= self.enemy_active_index:
                continue
            if not monster.is_fainted():
                return idx
        return None

    def first_available_switch(self) -> Optional[int]:
        for idx, monster in enumerate(self.player_party):
            if idx != self.active_index and not monster.is_fainted():
                return idx
        return None

    def queue_message(self, text: str, callback: Optional[Callable[[], None]] = None) -> None:
        self.message_queue.append({"text": text, "callback": callback})

    def pop_message(self) -> Optional[Dict[str, Optional[Callable[[], None]]]]:
        if self.message_queue:
            return self.message_queue.pop(0)
        return None


# ----------------------------------------------------------------------------
# Utility functions
# ----------------------------------------------------------------------------


def tile_at(x: int, y: int) -> str:
    if 0 <= y < MAP_HEIGHT and 0 <= x < MAP_WIDTH:
        return MAP_LAYOUT[y][x]
    return "#"


def can_walk(x: int, y: int) -> bool:
    tile = tile_at(x, y)
    return TILE_TYPES.get(tile, TILE_TYPES["#"])["walkable"]


def on_grass(x: int, y: int) -> bool:
    return tile_at(x, y) == "G"


def encounter_chance() -> bool:
    # Adjust this probability to balance encounter frequency.
    return random.random() < 0.1


def enemy_label(battle: BattleState, monster: Monster) -> str:
    """Return a readable label for the opposing monster based on battle type."""

    if getattr(battle, "trainer_info", None):
        trainer_name = battle.trainer_info.get("name", "Trainer")
        return f"{trainer_name}'s {monster.name}"
    return f"Wild {monster.name}"


def calculate_damage(attacker: Monster, defender: Monster, move: Move) -> int:
    base = move.power + attacker.attack - int(defender.defense * 0.5)
    base = max(base, 1)
    variance = random.uniform(0.85, 1.0)
    return max(1, int(base * variance))


def accuracy_check(move: Move) -> bool:
    return random.random() <= move.accuracy


def calculate_exp_gain(defeated: Monster) -> int:
    return 10 + defeated.level * 5


def start_battle(
    player_party: List[Monster],
    wild_monsters: List[Monster],
    max_party_size: int,
) -> BattleState:
    enemy_template = random.choice(wild_monsters)
    enemy = clone_monster(enemy_template)
    return BattleState(
        player_party=player_party,
        enemy_monster=enemy,
        max_party_size=max_party_size,
    )


def start_trainer_battle(
    trainer_id: str,
    trainers: Dict[str, Dict[str, object]],
    monster_templates: Dict[str, Monster],
    player_party: List[Monster],
    max_party_size: int,
) -> Optional[BattleState]:
    """Start a fixed trainer battle using the trainer's defined team."""

    trainer = trainers.get(trainer_id)
    if not trainer:
        return None

    enemy_party: List[Monster] = []
    for monster_name in trainer.get("team", []):
        template = monster_templates.get(monster_name)
        if template:
            enemy_party.append(clone_monster(template))

    if not enemy_party:
        return None

    battle = BattleState(
        player_party=player_party,
        enemy_monster=enemy_party[0],
        max_party_size=max_party_size,
        trainer=trainer,
        enemy_party=enemy_party,
    )

    for line in trainer.get("dialogue_before", []):
        battle.queue_message(f"{trainer['name']}: {line}")
    battle.queue_message(f"{trainer['name']} sent out {battle.enemy_monster.name}!")
    return battle


# ----------------------------------------------------------------------------
# Rendering helpers
# ----------------------------------------------------------------------------


def draw_text(surface: pygame.Surface, text: str, position: tuple[int, int], font: pygame.font.Font, color=(10, 10, 10)) -> None:
    rendered = font.render(text, True, color)
    surface.blit(rendered, position)

def draw_overworld(
    screen: pygame.Surface,
    player: Player,
    font: pygame.font.Font,
    message: Optional[str],
    tile_surfaces: Dict[str, pygame.Surface],
    player_sprite: pygame.Surface,
) -> None:
    screen.fill((76, 120, 160))

    player_center_x = player.tile_x * TILE_SIZE + TILE_SIZE // 2
    player_center_y = player.tile_y * TILE_SIZE + TILE_SIZE // 2

    max_cam_x = max(0, MAP_PIXEL_WIDTH - WINDOW_WIDTH)
    max_cam_y = max(0, MAP_PIXEL_HEIGHT - WINDOW_HEIGHT)
    cam_x = max(0, min(player_center_x - WINDOW_WIDTH // 2, max_cam_x))
    cam_y = max(0, min(player_center_y - WINDOW_HEIGHT // 2, max_cam_y))

    for y, row in enumerate(MAP_LAYOUT):
        for x, tile in enumerate(row):
            draw_x = x * TILE_SIZE - cam_x
            draw_y = y * TILE_SIZE - cam_y
            if draw_x + TILE_SIZE < 0 or draw_y + TILE_SIZE < 0:
                continue
            if draw_x >= WINDOW_WIDTH or draw_y >= WINDOW_HEIGHT:
                continue
            tile_surface = tile_surfaces.get(tile) or tile_surfaces.get("#")
            if tile_surface:
                screen.blit(tile_surface, (draw_x, draw_y))

    sprite_rect = player_sprite.get_rect()
    sprite_x = (
        player.tile_x * TILE_SIZE
        - cam_x
        + (TILE_SIZE - sprite_rect.width) // 2
    )
    sprite_y = (
        player.tile_y * TILE_SIZE
        - cam_y
        + (TILE_SIZE - sprite_rect.height) // 2
    )
    screen.blit(player_sprite, (sprite_x, sprite_y))

    hint_text = message or "Use arrow keys to explore. Walk on grass to find creatures!"
    hint_surface = pygame.Surface((WINDOW_WIDTH, 32), pygame.SRCALPHA)
    hint_surface.fill((0, 0, 0, 160))
    screen.blit(hint_surface, (0, WINDOW_HEIGHT - 32))
    draw_text(screen, hint_text, (12, WINDOW_HEIGHT - 26), font, color=(230, 230, 230))


def draw_hp_bar(surface: pygame.Surface, font: pygame.font.Font, monster: Monster, position: tuple[int, int]) -> None:
    x, y = position
    bar_width = 200
    bar_height = 20
    hp_ratio = monster.current_hp / monster.max_hp
    pygame.draw.rect(surface, (0, 0, 0), (x, y, bar_width, bar_height), 2)
    pygame.draw.rect(surface, (200, 60, 60), (x + 2, y + 2, int((bar_width - 4) * hp_ratio), bar_height - 4))
    draw_text(surface, f"{monster.name} Lv{monster.level}", (x, y - 22), font)
    draw_text(surface, f"HP: {monster.current_hp}/{monster.max_hp}", (x + 6, y + 2), font)


def draw_battle(screen: pygame.Surface, battle: BattleState, font: pygame.font.Font, small_font: pygame.font.Font) -> None:
    screen.fill((220, 220, 255))
    draw_hp_bar(screen, font, battle.player_monster, (40, 320))
    draw_hp_bar(screen, font, battle.enemy_monster, (360, 120))
    draw_text(
        screen,
        f"EXP: {battle.player_monster.exp}/{battle.player_monster.exp_to_next}",
        (40, 350),
        small_font,
    )

    def blit_or_placeholder(monster: Monster, position: tuple[int, int], fallback_color: tuple[int, int, int]) -> None:
        sprite = monster.front_sprite
        if monster is battle.player_monster:
            sprite = monster.back_sprite or monster.front_sprite
        if sprite:
            rect = sprite.get_rect(center=position)
            screen.blit(sprite, rect)
        else:
            pygame.draw.circle(screen, fallback_color, position, 48)

    blit_or_placeholder(battle.player_monster, (140, 280), (255, 120, 80))
    blit_or_placeholder(battle.enemy_monster, (500, 200), (80, 180, 255))

    # Draw battle menu area
    menu_rect = pygame.Rect(20, 360, 600, 100)
    pygame.draw.rect(screen, (245, 245, 245), menu_rect)
    pygame.draw.rect(screen, (0, 0, 0), menu_rect, 2)

    current_message = battle.message_queue[0]["text"] if battle.message_queue else None

    if current_message:
        draw_text(screen, current_message, (menu_rect.x + 12, menu_rect.y + 12), small_font)
    elif battle.menu_state == "action":
        for idx, option in enumerate(battle.action_options):
            prefix = "> " if idx == battle.action_index else "  "
            label = option
            if option == "Catch" and battle.party_size >= battle.max_party_size:
                label = f"{option} (Send to storage)"
            if option == "Switch" and not battle.available_switch_targets():
                label = f"{option} (Unavailable)"
            draw_text(
                screen,
                prefix + label,
                (menu_rect.x + 12, menu_rect.y + 12 + idx * 24),
                small_font,
            )
    elif battle.menu_state == "move":
        for idx, move in enumerate(battle.player_monster.moves):
            prefix = "> " if idx == battle.move_index else "  "
            text = f"{prefix}{move.name} ({int(move.accuracy * 100)}% accuracy)"
            draw_text(screen, text, (menu_rect.x + 12, menu_rect.y + 12 + idx * 24), small_font)
    elif battle.menu_state == "switch":
        draw_text(
            screen,
            "Choose a monster to send out.",
            (menu_rect.x + 12, menu_rect.y + 12),
            small_font,
        )
        for idx, monster in enumerate(battle.player_party):
            prefix = "> " if idx == battle.switch_index else "  "
            status = "Fainted" if monster.is_fainted() else f"HP {monster.current_hp}/{monster.max_hp}"
            active_note = " (Active)" if idx == battle.active_index else ""
            line = f"{prefix}{monster.name} Lv{monster.level} - {status}{active_note}"
            draw_text(
                screen,
                line,
                (menu_rect.x + 12, menu_rect.y + 36 + idx * 22),
                small_font,
            )


def draw_party_menu(
    screen: pygame.Surface,
    party: List[Monster],
    storage: List[Monster],
    font: pygame.font.Font,
    small_font: pygame.font.Font,
    party_index: int,
    storage_index: int,
    view: str,
    reorder_source: Optional[int],
) -> None:
    overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 160))
    screen.blit(overlay, (0, 0))

    panel_rect = pygame.Rect(50, 50, WINDOW_WIDTH - 100, WINDOW_HEIGHT - 100)
    pygame.draw.rect(screen, (245, 245, 245), panel_rect)
    pygame.draw.rect(screen, (0, 0, 0), panel_rect, 2)

    title = "Party Status" if view == "party" else "Storage"
    draw_text(screen, title, (panel_rect.x + 20, panel_rect.y + 16), font)

    if view == "party":
        if reorder_source is None:
            hint = (
                "UP/DOWN to inspect · ENTER to reorder · D to send to storage · LEFT/RIGHT to change view · TAB/P to close · S to save"
            )
        else:
            hint = (
                "Choose swap target with UP/DOWN · ENTER to confirm · ESC to cancel · TAB/P to close"
            )
    else:
        hint = (
            "UP/DOWN to inspect · W to withdraw to party · LEFT/RIGHT to change view · TAB/P to close · S to save"
        )

    draw_text(screen, hint, (panel_rect.x + 20, panel_rect.y + 46), small_font)

    list_rect = pygame.Rect(panel_rect.x + 20, panel_rect.y + 80, 280, panel_rect.height - 100)
    detail_x = list_rect.right + 30

    if view == "party":
        for idx in range(MAX_PARTY_SIZE):
            if idx < len(party):
                monster = party[idx]
                prefix = ">" if idx == party_index else " "
                if reorder_source == idx:
                    prefix = "*"
                status = "FNT" if monster.is_fainted() else f"HP {monster.current_hp}/{monster.max_hp}"
                suffix = ""
                if reorder_source == idx:
                    suffix = " [Selected]"
                elif reorder_source is not None and idx == party_index:
                    suffix = " [Swap]"
                draw_text(
                    screen,
                    f"{prefix} Slot {idx + 1}: {monster.name} Lv{monster.level} ({status}){suffix}",
                    (list_rect.x, list_rect.y + idx * 28),
                    font,
                )
            else:
                draw_text(
                    screen,
                    f"  Slot {idx + 1}: --- Empty ---",
                    (list_rect.x, list_rect.y + idx * 28),
                    font,
                )

        if not party:
            draw_text(screen, "Your party is empty!", (detail_x, list_rect.y), font)
            return

        party_index = max(0, min(party_index, len(party) - 1))
        selected = party[party_index]
    else:
        total_storage = len(storage)
        if total_storage == 0:
            draw_text(screen, "Storage is empty.", (list_rect.x, list_rect.y), font)
            selected = None
        else:
            storage_index = max(0, min(storage_index, total_storage - 1))
            visible_rows = 8
            top_index = 0
            if total_storage > visible_rows:
                top_index = max(0, min(storage_index - visible_rows // 2, total_storage - visible_rows))
            for row in range(visible_rows):
                actual_index = top_index + row
                if actual_index >= total_storage:
                    break
                monster = storage[actual_index]
                prefix = ">" if actual_index == storage_index else " "
                draw_text(
                    screen,
                    f"{prefix} Crate {actual_index + 1}: {monster.name} Lv{monster.level}",
                    (list_rect.x, list_rect.y + row * 28),
                    font,
                )
            selected = storage[storage_index]

    if not selected:
        return

    stats_y = list_rect.y
    draw_text(screen, f"Name: {selected.name}", (detail_x, stats_y), font)
    draw_text(screen, f"Type: {selected.type}", (detail_x, stats_y + 26), font)
    draw_text(
        screen,
        f"Level {selected.level}  EXP {selected.exp}/{selected.exp_to_next}",
        (detail_x, stats_y + 52),
        small_font,
    )
    draw_text(
        screen,
        f"HP {selected.current_hp}/{selected.max_hp}  ATK {selected.attack}  DEF {selected.defense}  SPD {selected.speed}",
        (detail_x, stats_y + 78),
        small_font,
    )

    sprite = selected.front_sprite or selected.back_sprite
    if sprite:
        sprite_rect = sprite.get_rect()
        sprite_rect.topleft = (detail_x, stats_y + 110)
        screen.blit(sprite, sprite_rect)

    draw_text(screen, "Moves:", (detail_x, stats_y + 220), font)
    for idx, move in enumerate(selected.moves):
        draw_text(
            screen,
            f"{move.name}  Pow {move.power}  Acc {int(move.accuracy * 100)}%",
            (detail_x, stats_y + 246 + idx * 24),
            small_font,
    )


def starter_selection_screen(
    screen: pygame.Surface,
    font: pygame.font.Font,
    small_font: pygame.font.Font,
    clock: pygame.time.Clock,
    starter_names: List[str],
    monster_templates: Dict[str, Monster],
) -> Optional[str]:
    """Show a simple starter selection menu and return the chosen monster name."""

    selection = 0
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return None
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_UP:
                    selection = (selection - 1) % len(starter_names)
                elif event.key == pygame.K_DOWN:
                    selection = (selection + 1) % len(starter_names)
                elif event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_z):
                    return starter_names[selection]

        screen.fill((68, 128, 120))
        panel = pygame.Rect(60, 60, WINDOW_WIDTH - 120, WINDOW_HEIGHT - 120)
        pygame.draw.rect(screen, (236, 236, 236), panel)
        pygame.draw.rect(screen, (0, 0, 0), panel, 2)
        draw_text(screen, "Choose your starter companion!", (panel.x + 20, panel.y + 16), font)
        draw_text(
            screen,
            "Up/Down to browse · Enter to confirm",
            (panel.x + 20, panel.y + 44),
            small_font,
        )

        for idx, name in enumerate(starter_names):
            template = monster_templates.get(name)
            type_label = template.type if template else "Unknown"
            stats = (
                f"HP {template.max_hp} · ATK {template.attack} · DEF {template.defense} · SPD {template.speed}"
                if template
                else ""
            )
            prefix = "> " if idx == selection else "  "
            draw_text(
                screen,
                f"{prefix}{name} ({type_label})",
                (panel.x + 24, panel.y + 84 + idx * 60),
                font,
            )
            if stats:
                draw_text(screen, stats, (panel.x + 44, panel.y + 110 + idx * 60), small_font)

        pygame.display.flip()
        clock.tick(60)


# ----------------------------------------------------------------------------
# Battle flow control
# ----------------------------------------------------------------------------


def handle_battle_input(event: pygame.event.Event, battle: BattleState) -> None:
    if battle.message_queue:
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_SPACE, pygame.K_RETURN, pygame.K_z):
            message = battle.pop_message()
            if message and message["callback"]:
                message["callback"]()
            # After message callbacks run, check whether enemy turn should start
            if not battle.message_queue and battle.pending_enemy_turn:
                battle.pending_enemy_turn = False
                execute_enemy_turn(battle)
            elif not battle.message_queue and battle.after_battle_callback:
                callback = battle.after_battle_callback
                battle.after_battle_callback = None
                callback()
        return

    if event.type != pygame.KEYDOWN:
        return

    if battle.force_switch:
        if not battle.available_switch_targets():
            battle.force_switch = False
            battle.queue_message("All of your monsters have fainted!")
            battle.after_battle_callback = lambda: setattr(battle, "ended", True)
            return
        if battle.menu_state != "switch":
            first_option = battle.first_available_switch()
            if first_option is not None:
                battle.switch_index = first_option
            battle.menu_state = "switch"

    if battle.menu_state == "action":
        if event.key in (pygame.K_UP, pygame.K_DOWN):
            option_count = len(battle.action_options)
            battle.action_index = (
                battle.action_index + (1 if event.key == pygame.K_DOWN else -1)
            ) % option_count
        elif event.key in (pygame.K_RETURN, pygame.K_z, pygame.K_SPACE):
            selected_option = battle.action_options[battle.action_index]
            if selected_option == "Fight":
                battle.menu_state = "move"
                battle.move_index = 0
            elif selected_option == "Switch":
                targets = battle.available_switch_targets()
                if not targets:
                    battle.queue_message("No other monsters can fight!")
                else:
                    if battle.switch_index not in targets:
                        battle.switch_index = targets[0]
                    battle.menu_state = "switch"
            elif selected_option == "Catch":
                attempt_capture(battle)
            else:
                attempt_escape(battle)
    elif battle.menu_state == "move":
        moves_len = len(battle.player_monster.moves)
        if event.key == pygame.K_UP:
            battle.move_index = (battle.move_index - 1) % moves_len
        elif event.key == pygame.K_DOWN:
            battle.move_index = (battle.move_index + 1) % moves_len
        elif event.key == pygame.K_ESCAPE:
            battle.menu_state = "action"
        elif event.key in (pygame.K_RETURN, pygame.K_z, pygame.K_SPACE):
            selected_move = battle.player_monster.moves[battle.move_index]
            execute_player_turn(battle, selected_move)
    elif battle.menu_state == "switch":
        party_len = battle.party_size
        if party_len == 0:
            return
        if event.key == pygame.K_UP:
            battle.switch_index = (battle.switch_index - 1) % party_len
        elif event.key == pygame.K_DOWN:
            battle.switch_index = (battle.switch_index + 1) % party_len
        elif event.key == pygame.K_ESCAPE:
            if not battle.force_switch:
                battle.menu_state = "action"
        elif event.key in (pygame.K_RETURN, pygame.K_z, pygame.K_SPACE):
            if battle.switch_index == battle.active_index:
                battle.queue_message("That monster is already in battle!")
                return
            chosen = battle.player_party[battle.switch_index]
            if chosen.is_fainted():
                battle.queue_message(f"{chosen.name} can't fight!")
                return
            perform_player_switch(battle, battle.switch_index, costs_turn=not battle.force_switch)


def perform_player_switch(battle: BattleState, new_index: int, costs_turn: bool) -> None:
    battle.set_active_monster(new_index)
    battle.force_switch = False
    battle.menu_state = "action"
    battle.action_index = 0
    battle.move_index = 0
    battle.pending_enemy_turn = costs_turn
    battle.queue_message(f"Go {battle.player_monster.name}!")


def execute_player_turn(battle: BattleState, move: Move) -> None:
    attacker = battle.player_monster
    defender = battle.enemy_monster

    if not accuracy_check(move):
        battle.queue_message(f"{attacker.name}'s {move.name} missed!")
    else:
        damage = calculate_damage(attacker, defender, move)
        defender.current_hp = max(0, defender.current_hp - damage)
        battle.queue_message(f"{attacker.name} used {move.name}!")
        battle.queue_message(f"It dealt {damage} damage!")

        if defender.is_fainted():
            exp_gain = calculate_exp_gain(defender)

            def handle_trainer_follow_up() -> None:
                if not battle.trainer_info:
                    battle.after_battle_callback = lambda: setattr(battle, "ended", True)
                    return

                trainer_name = battle.trainer_info.get("name", "Trainer")
                next_index = battle.next_enemy_index()
                if next_index is None:
                    battle.trainer_defeated = True
                    if battle.trainer_info.get("is_gym_leader") and battle.trainer_info.get("badge_name"):
                        battle.badge_earned = str(battle.trainer_info.get("badge_name"))

                    def finish_battle() -> None:
                        battle.after_battle_callback = lambda: setattr(battle, "ended", True)

                    after_dialogue = battle.trainer_info.get("dialogue_after", [])
                    if after_dialogue:
                        for idx, line in enumerate(after_dialogue):
                            callback = finish_battle if idx == len(after_dialogue) - 1 else None
                            battle.queue_message(f"{trainer_name}: {line}", callback=callback)
                    else:
                        finish_battle()
                else:
                    battle.set_enemy_monster(next_index)
                    battle.queue_message(f"{trainer_name} sent out {battle.enemy_monster.name}!")

            def award_exp() -> None:
                level_messages = attacker.gain_experience(exp_gain)
                for message in level_messages:
                    battle.queue_message(message)
                handle_trainer_follow_up()

            battle.queue_message(f"{enemy_label(battle, defender)} fainted!")
            battle.queue_message(f"{attacker.name} gained {exp_gain} EXP!", callback=award_exp)
            battle.pending_enemy_turn = False
            battle.menu_state = "action"
            battle.action_index = 0
            return

    battle.pending_enemy_turn = True
    battle.menu_state = "action"
    battle.action_index = 0


def execute_enemy_turn(battle: BattleState) -> None:
    attacker = battle.enemy_monster
    defender = battle.player_monster
    move = random.choice(attacker.moves)

    if not accuracy_check(move):
        battle.queue_message(f"{enemy_label(battle, attacker)}'s {move.name} missed!")
    else:
        damage = calculate_damage(attacker, defender, move)
        defender.current_hp = max(0, defender.current_hp - damage)
        battle.queue_message(f"{enemy_label(battle, attacker)} used {move.name}!")
        battle.queue_message(f"It dealt {damage} damage!")
        if defender.is_fainted():
            def handle_faint() -> None:
                next_option = battle.first_available_switch()
                if next_option is not None:
                    battle.force_switch = True
                    battle.menu_state = "switch"
                    battle.switch_index = next_option
                else:
                    battle.after_battle_callback = lambda: setattr(battle, "ended", True)

            battle.queue_message(f"{defender.name} fainted!", callback=handle_faint)


def attempt_capture(battle: BattleState) -> None:
    if battle.trainer_info:
        battle.queue_message("You can't capture a trainer's partner!")
        battle.pending_enemy_turn = True
        battle.menu_state = "action"
        battle.action_index = 0
        return

    battle.queue_message("You threw a capture charm!")

    enemy = battle.enemy_monster
    hp_ratio = enemy.current_hp / enemy.max_hp if enemy.max_hp else 1.0
    catch_chance = 0.3 + (1.0 - hp_ratio) * 0.5
    if random.random() <= catch_chance:

        def finish_capture() -> None:
            battle.captured_monster = clone_monster(enemy)
            battle.captured_to_storage = battle.party_size >= battle.max_party_size
            if battle.captured_to_storage:
                battle.queue_message(f"{enemy.name} will be sent to storage.")
            battle.after_battle_callback = lambda: setattr(battle, "ended", True)

        battle.queue_message(f"You caught {enemy.name}!", callback=finish_capture)
        battle.pending_enemy_turn = False
    else:
        battle.queue_message(f"{enemy.name} broke free!")
        battle.pending_enemy_turn = True

    battle.menu_state = "action"
    battle.action_index = 0


def attempt_escape(battle: BattleState) -> None:
    if battle.trainer_info:
        battle.queue_message("The trainer blocks your escape!")
        battle.pending_enemy_turn = True
        return
    if random.random() < 0.5:
        battle.queue_message("Got away safely!", callback=lambda: setattr(battle, "ended", True))
    else:
        battle.queue_message("Couldn't escape!")
        battle.pending_enemy_turn = True


# ----------------------------------------------------------------------------
# Main game loop
# ----------------------------------------------------------------------------


def main() -> None:
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption("Mythic Bond Prototype")
    clock = pygame.time.Clock()
    font = pygame.font.Font(None, 24)
    small_font = pygame.font.Font(None, 20)
    tile_surfaces = build_tile_surfaces(TILE_TYPES, TILE_SIZE)
    player_sprite = create_player_sprite(TILE_SIZE)

    move_library, monster_templates = load_monster_definitions()
    trainers = load_trainers()
    template_list = list(monster_templates.values())
    starter_names = ["Flarekit", "Dripfin", "Spriglet"]

    default_party: List[Monster] = []
    if not SAVE_FILE.exists():
        chosen = starter_selection_screen(
            screen, font, small_font, clock, starter_names, monster_templates
        )
        if chosen and chosen in monster_templates:
            default_party = [clone_monster(monster_templates[chosen])]

    if not default_party:
        default_party = [clone_monster(monster) for monster in template_list[:3]]
    if not default_party:
        raise ValueError("No monsters defined in monsters.json. Add at least one monster entry.")
    player_position, player_party, player_storage, badges, defeated_trainers = load_game_state(
        SAVE_FILE, monster_templates, default_party, DEFAULT_START_POSITION
    )
    earned_badges: Set[str] = set(badges)
    defeated_trainers_set: Set[str] = set(defeated_trainers)
    player_party = player_party[:MAX_PARTY_SIZE]
    player_storage = list(player_storage)
    if not player_party:
        raise ValueError("Unable to load a valid party from monsters.json or save data.")
    wild_pool = template_list

    player = Player(tile_x=player_position[0], tile_y=player_position[1])
    game_mode = "overworld"
    active_battle: Optional[BattleState] = None
    overworld_message: Optional[str] = None
    overworld_message_timer = 0
    party_selection = 0
    storage_selection = 0
    party_menu_view = "party"
    party_reorder_source: Optional[int] = None

    def end_battle() -> None:
        nonlocal game_mode, active_battle, overworld_message, overworld_message_timer, player_storage, earned_badges, defeated_trainers_set
        if not active_battle:
            return
        if all(monster.is_fainted() for monster in player_party):
            for monster in player_party:
                monster.heal()
            overworld_message = "Your party was revived after the battle!"
            overworld_message_timer = 240

        if active_battle.captured_monster:
            captured = active_battle.captured_monster
            if active_battle.captured_to_storage:
                player_storage.append(captured)
                overworld_message = f"{captured.name} was sent to storage!"
            elif len(player_party) < MAX_PARTY_SIZE:
                player_party.append(captured)
                overworld_message = f"{captured.name} joined your party!"
            else:
                player_storage.append(captured)
                overworld_message = f"{captured.name} was sent to storage!"
            overworld_message_timer = 240

        if active_battle.trainer_defeated and active_battle.trainer_id:
            defeated_trainers_set.add(active_battle.trainer_id)
            trainer_name = None
            if active_battle.trainer_info:
                trainer_name = active_battle.trainer_info.get("name")
            if active_battle.badge_earned:
                earned_badges.add(active_battle.badge_earned)
                overworld_message = f"You received the {active_battle.badge_earned}!"
                overworld_message_timer = 240
            elif trainer_name:
                overworld_message = f"{trainer_name} was defeated!"
                overworld_message_timer = 180
        game_mode = "overworld"
        active_battle = None

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif game_mode == "overworld" and event.type == pygame.KEYDOWN:
                if event.key == pygame.K_s:
                    save_game_state(
                        SAVE_FILE,
                        player,
                        player_party,
                        player_storage,
                        list(earned_badges),
                        list(defeated_trainers_set),
                    )
                    overworld_message = "Game saved!"
                    overworld_message_timer = 180
                    continue

                if event.key in (pygame.K_p, pygame.K_TAB):
                    if player_party:
                        party_selection = max(0, min(party_selection, len(player_party) - 1))
                    else:
                        party_selection = 0
                    game_mode = "party_menu"
                    party_menu_view = "party"
                    party_reorder_source = None
                    continue

                dx, dy = 0, 0
                if event.key == pygame.K_UP:
                    dy = -1
                elif event.key == pygame.K_DOWN:
                    dy = 1
                elif event.key == pygame.K_LEFT:
                    dx = -1
                elif event.key == pygame.K_RIGHT:
                    dx = 1

                if dx or dy:
                    new_x = player.tile_x + dx
                    new_y = player.tile_y + dy
                    if can_walk(new_x, new_y):
                        player.tile_x = new_x
                        player.tile_y = new_y
                        tile_symbol = tile_at(new_x, new_y)
                        if tile_symbol == "H":
                            for monster in player_party:
                                monster.heal()
                            overworld_message = "Your party was restored at the roadside house!"
                            overworld_message_timer = 180
                        trainer_id = TRAINER_TILES.get(tile_symbol)
                        if (
                            trainer_id
                            and trainer_id in trainers
                            and trainer_id not in defeated_trainers_set
                        ):
                            battle = start_trainer_battle(
                                trainer_id, trainers, monster_templates, player_party, MAX_PARTY_SIZE
                            )
                            if battle:
                                game_mode = "battle"
                                active_battle = battle
                                overworld_message = None
                                continue
                            else:
                                overworld_message = "Trainer data missing."
                                overworld_message_timer = 180
                        if tile_symbol == "G" and encounter_chance():
                            game_mode = "battle"
                            active_battle = start_battle(
                                player_party,
                                wild_pool,
                                MAX_PARTY_SIZE,
                            )
                            overworld_message = None

            elif game_mode == "battle" and active_battle:
                handle_battle_input(event, active_battle)
            elif game_mode == "party_menu" and event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_ESCAPE, pygame.K_p, pygame.K_TAB):
                    if party_reorder_source is not None:
                        party_reorder_source = None
                    else:
                        game_mode = "overworld"
                elif event.key == pygame.K_s:
                    save_game_state(
                        SAVE_FILE,
                        player,
                        player_party,
                        player_storage,
                        list(earned_badges),
                        list(defeated_trainers_set),
                    )
                    overworld_message = "Game saved!"
                    overworld_message_timer = 180
                elif event.key in (pygame.K_LEFT, pygame.K_RIGHT):
                    party_reorder_source = None
                    party_menu_view = "storage" if party_menu_view == "party" else "party"
                elif event.key == pygame.K_UP:
                    if party_menu_view == "party" and player_party:
                        party_selection = (party_selection - 1) % len(player_party)
                    elif party_menu_view == "storage" and player_storage:
                        storage_selection = (storage_selection - 1) % len(player_storage)
                elif event.key == pygame.K_DOWN:
                    if party_menu_view == "party" and player_party:
                        party_selection = (party_selection + 1) % len(player_party)
                    elif party_menu_view == "storage" and player_storage:
                        storage_selection = (storage_selection + 1) % len(player_storage)
                elif event.key == pygame.K_d and party_menu_view == "party" and player_party:
                    if len(player_party) <= 1:
                        overworld_message = "You need at least one monster in your party."
                        overworld_message_timer = 180
                    else:
                        monster = player_party.pop(party_selection)
                        player_storage.append(monster)
                        party_selection = max(0, min(party_selection, len(player_party) - 1))
                        party_reorder_source = None
                        overworld_message = f"{monster.name} was sent to storage."
                        overworld_message_timer = 180
                elif event.key == pygame.K_w and party_menu_view == "storage" and player_storage:
                    if len(player_party) >= MAX_PARTY_SIZE:
                        overworld_message = "Party is full. Release a slot first."
                        overworld_message_timer = 180
                    else:
                        monster = player_storage.pop(storage_selection)
                        player_party.append(monster)
                        if player_storage:
                            storage_selection = max(0, min(storage_selection, len(player_storage) - 1))
                        else:
                            storage_selection = 0
                        overworld_message = f"{monster.name} joined your party."
                        overworld_message_timer = 180
                elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    if party_menu_view == "party" and player_party:
                        if party_reorder_source is None:
                            party_reorder_source = party_selection
                        else:
                            if party_selection != party_reorder_source:
                                player_party[party_reorder_source], player_party[party_selection] = (
                                    player_party[party_selection],
                                    player_party[party_reorder_source],
                                )
                            party_reorder_source = None
                elif event.key == pygame.K_BACKSPACE:
                    if party_reorder_source is not None:
                        party_reorder_source = None

        screen.fill((0, 0, 0))

        if game_mode == "overworld":
            draw_overworld(screen, player, font, overworld_message, tile_surfaces, player_sprite)
        elif game_mode == "battle" and active_battle:
            draw_battle(screen, active_battle, font, small_font)
            if getattr(active_battle, "ended", False) and not active_battle.message_queue and not active_battle.pending_enemy_turn:
                end_battle()
        elif game_mode == "party_menu":
            draw_overworld(screen, player, font, overworld_message, tile_surfaces, player_sprite)
            draw_party_menu(
                screen,
                player_party,
                player_storage,
                font,
                small_font,
                party_selection,
                storage_selection,
                party_menu_view,
                party_reorder_source,
            )

        if overworld_message_timer > 0:
            overworld_message_timer -= 1
            if overworld_message_timer == 0:
                overworld_message = None

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()


"""
Quick reference:
  - Run the game with: python main.py
  - Add or tweak monsters in assets/monsters.json (sprites go in assets/sprites)
  - Add new moves inside create_move_library.
  - Edit MAP_LAYOUT and TILE_TYPES to build new areas (the camera will scroll to
    fit whatever size you design).
"""
