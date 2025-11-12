# Install pygame with: pip install pygame
# Run the game with: python main.py

import json
import random
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional

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
SAVE_FILE = Path(__file__).parent / "savegame.json"

MAX_PARTY_SIZE = 6


def create_move_library() -> Dict[str, Move]:
    """Return the core move definitions. Extend this to add new moves."""
    return {
        "Cinder Snap": Move("Cinder Snap", power=18, accuracy=0.95, type="ember"),
        "Leaf Gust": Move("Leaf Gust", power=16, accuracy=0.9, type="flora"),
        "Ripple Shot": Move("Ripple Shot", power=20, accuracy=0.85, type="aqua"),
        "Nuzzle": Move("Nuzzle", power=10, accuracy=1.0, type="normal"),
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
    path: Path, player: "Player", party: List[Monster], storage: List[Monster]
) -> None:
    data = {
        "player": {"x": player.tile_x, "y": player.tile_y},
        "party": [monster_to_dict(monster) for monster in party[:MAX_PARTY_SIZE]],
        "storage": [monster_to_dict(monster) for monster in storage],
    }
    path.write_text(json.dumps(data, indent=2))


def load_game_state(
    path: Path,
    templates: Dict[str, Monster],
    default_party: List[Monster],
    default_position: tuple[int, int],
) -> tuple[tuple[int, int], List[Monster], List[Monster]]:
    if not path.exists():
        return default_position, list(default_party), []

    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError:
        return default_position, list(default_party), []

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

    return player_position, loaded_party, loaded_storage


# ----------------------------------------------------------------------------
# Overworld definitions: map data, tiles, and player movement helpers
# ----------------------------------------------------------------------------

TILE_SIZE = 32
WINDOW_WIDTH, WINDOW_HEIGHT = 640, 480
MAP_LAYOUT = [
    "####################",
    "#....GGGGGG....GG..#",
    "#..######....####..#",
    "#..#....#....#..#..#",
    "#..#....#....#..#..#",
    "#....CCCCCCCC......#",
    "#....C......C..GG..#",
    "#....C.DD..D.C.....#",
    "#....CCCCCCCC......#",
    "#..................#",
    "#.SSS......GGGG....#",
    "#.SHS......GGGG....#",
    "#.SDS......GGGG....#",
    "#..................#",
    "####################",
]
MAP_WIDTH = len(MAP_LAYOUT[0])
MAP_HEIGHT = len(MAP_LAYOUT)
DEFAULT_START_POSITION = (2, 2)

TILE_TYPES = {
    "#": {"color": (70, 70, 70), "walkable": False, "name": "Wall"},
    ".": {"color": (200, 200, 160), "walkable": True, "name": "Ground"},
    "G": {"color": (120, 200, 120), "walkable": True, "name": "Grass"},
    "C": {"color": (150, 150, 180), "walkable": False, "name": "Great Hall"},
    "D": {"color": (230, 210, 150), "walkable": True, "name": "Door"},
    "S": {"color": (140, 140, 170), "walkable": False, "name": "House Wall"},
    "H": {"color": (170, 230, 200), "walkable": True, "name": "Healing Floor"},
}


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
    ):
        if not player_party:
            raise ValueError("Player party cannot be empty when a battle begins.")
        if all(monster.is_fainted() for monster in player_party):
            raise ValueError("All party monsters have fainted and cannot battle.")

        self.player_party = player_party
        self.enemy_monster = enemy_monster
        self.max_party_size = max_party_size

        self.active_index = next(
            (idx for idx, monster in enumerate(self.player_party) if not monster.is_fainted()),
            0,
        )
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
        self.action_options: List[str] = ["Fight", "Switch", "Catch", "Run"]
        self.captured_monster: Optional[Monster] = None
        self.captured_to_storage = False

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


# ----------------------------------------------------------------------------
# Rendering helpers
# ----------------------------------------------------------------------------


def draw_text(surface: pygame.Surface, text: str, position: tuple[int, int], font: pygame.font.Font, color=(10, 10, 10)) -> None:
    rendered = font.render(text, True, color)
    surface.blit(rendered, position)


def draw_overworld(screen: pygame.Surface, player: Player, font: pygame.font.Font, message: Optional[str]) -> None:
    for y, row in enumerate(MAP_LAYOUT):
        for x, tile in enumerate(row):
            tile_info = TILE_TYPES[tile]
            rect = pygame.Rect(x * TILE_SIZE, y * TILE_SIZE, TILE_SIZE, TILE_SIZE)
            pygame.draw.rect(screen, tile_info["color"], rect)
            pygame.draw.rect(screen, (30, 30, 30), rect, 1)

    pygame.draw.rect(screen, (220, 60, 60), player.rect())
    hint = message or "Use arrow keys to explore. Walk on grass to find creatures!"
    draw_text(screen, hint, (10, WINDOW_HEIGHT - 25), font)


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
) -> None:
    overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 160))
    screen.blit(overlay, (0, 0))

    panel_rect = pygame.Rect(50, 50, WINDOW_WIDTH - 100, WINDOW_HEIGHT - 100)
    pygame.draw.rect(screen, (245, 245, 245), panel_rect)
    pygame.draw.rect(screen, (0, 0, 0), panel_rect, 2)

    title = "Party Status" if view == "party" else "Storage"
    draw_text(screen, title, (panel_rect.x + 20, panel_rect.y + 16), font)
    draw_text(
        screen,
        "UP/DOWN to inspect · LEFT/RIGHT to change view · TAB/P to close · S to save",
        (panel_rect.x + 20, panel_rect.y + 46),
        small_font,
    )

    list_rect = pygame.Rect(panel_rect.x + 20, panel_rect.y + 80, 280, panel_rect.height - 100)
    detail_x = list_rect.right + 30

    if view == "party":
        for idx in range(MAX_PARTY_SIZE):
            if idx < len(party):
                monster = party[idx]
                prefix = ">" if idx == party_index else " "
                status = "FNT" if monster.is_fainted() else f"HP {monster.current_hp}/{monster.max_hp}"
                draw_text(
                    screen,
                    f"{prefix} Slot {idx + 1}: {monster.name} Lv{monster.level} ({status})",
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

            def award_exp() -> None:
                level_messages = attacker.gain_experience(exp_gain)
                for message in level_messages:
                    battle.queue_message(message)
                battle.after_battle_callback = lambda: setattr(battle, "ended", True)

            battle.queue_message(f"Wild {defender.name} fainted!")
            battle.queue_message(f"{attacker.name} gained {exp_gain} EXP!", callback=award_exp)
            battle.pending_enemy_turn = False
            return

    battle.pending_enemy_turn = True
    battle.menu_state = "action"
    battle.action_index = 0


def execute_enemy_turn(battle: BattleState) -> None:
    attacker = battle.enemy_monster
    defender = battle.player_monster
    move = random.choice(attacker.moves)

    if not accuracy_check(move):
        battle.queue_message(f"Wild {attacker.name}'s {move.name} missed!")
    else:
        damage = calculate_damage(attacker, defender, move)
        defender.current_hp = max(0, defender.current_hp - damage)
        battle.queue_message(f"Wild {attacker.name} used {move.name}!")
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

    move_library = create_move_library()
    monster_templates = create_monster_templates(move_library)
    template_list = list(monster_templates.values())
    default_party = [clone_monster(monster) for monster in template_list[:3]]
    if not default_party:
        raise ValueError("No monsters defined in monsters.json. Add at least one monster entry.")
    player_position, player_party, player_storage = load_game_state(
        SAVE_FILE, monster_templates, default_party, DEFAULT_START_POSITION
    )
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

    def end_battle() -> None:
        nonlocal game_mode, active_battle, overworld_message, overworld_message_timer, player_storage
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
        game_mode = "overworld"
        active_battle = None

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif game_mode == "overworld" and event.type == pygame.KEYDOWN:
                if event.key == pygame.K_s:
                    save_game_state(SAVE_FILE, player, player_party, player_storage)
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
                    game_mode = "overworld"
                elif event.key == pygame.K_s:
                    save_game_state(SAVE_FILE, player, player_party, player_storage)
                    overworld_message = "Game saved!"
                    overworld_message_timer = 180
                elif event.key in (pygame.K_LEFT, pygame.K_RIGHT):
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

        screen.fill((0, 0, 0))

        if game_mode == "overworld":
            draw_overworld(screen, player, font, overworld_message)
        elif game_mode == "battle" and active_battle:
            draw_battle(screen, active_battle, font, small_font)
            if getattr(active_battle, "ended", False) and not active_battle.message_queue and not active_battle.pending_enemy_turn:
                end_battle()
        elif game_mode == "party_menu":
            draw_overworld(screen, player, font, overworld_message)
            draw_party_menu(
                screen,
                player_party,
                player_storage,
                font,
                small_font,
                party_selection,
                storage_selection,
                party_menu_view,
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
  - Edit MAP_LAYOUT and TILE_TYPES to build new areas.
"""
