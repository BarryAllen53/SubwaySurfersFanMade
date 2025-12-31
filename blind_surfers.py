import os
import random
import sys
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import pygame
from accessible_output2 import outputs


SOUND_DIR = os.path.join(os.path.dirname(__file__), "sounds")

LANES = [0, 1, 2]
LANE_PAN = {0: -0.8, 1: 0.0, 2: 0.8}

SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
FPS = 60

MAX_DISTANCE = 100.0


class TTS:
    def __init__(self) -> None:
        self.speaker = outputs.auto.Auto()

    def say(self, text: str) -> None:
        try:
            self.speaker.speak(text)
        except Exception as exc:  # pragma: no cover - TTS should not crash game
            print(f"TTS warning: {exc}")


class SoundManager:
    def __init__(self, tts: TTS) -> None:
        self.tts = tts
        self.sounds: Dict[str, pygame.mixer.Sound] = {}
        self.music_volume = 0.8
        self.sfx_volume = 0.9
        self.looping_sounds: Dict[str, pygame.mixer.Channel] = {}

    def _resolve_path(self, name: str) -> Optional[str]:
        if os.path.splitext(name)[1]:
            path = os.path.join(SOUND_DIR, name)
            return path if os.path.exists(path) else None
        for ext in (".ogg", ".wav", ".mp3"):
            path = os.path.join(SOUND_DIR, f"{name}{ext}")
            if os.path.exists(path):
                return path
        return None

    def load_sound(self, name: str) -> Optional[pygame.mixer.Sound]:
        if name in self.sounds:
            return self.sounds[name]
        path = self._resolve_path(name)
        if not path:
            print(f"Warning: sound asset missing for {name}")
            return None
        try:
            sound = pygame.mixer.Sound(path)
        except pygame.error as exc:
            print(f"Warning: failed to load sound {path}: {exc}")
            return None
        self.sounds[name] = sound
        return sound

    def play_sound(
        self,
        name: str,
        lane: int = 1,
        distance: float = MAX_DISTANCE,
        loops: int = 0,
    ) -> None:
        sound = self.load_sound(name)
        if not sound:
            return
        channel = pygame.mixer.find_channel(True)
        if not channel:
            return
        left, right = self._pan_to_stereo(LANE_PAN.get(lane, 0.0))
        volume = self._distance_to_volume(distance) * self.sfx_volume
        channel.set_volume(left * volume, right * volume)
        channel.play(sound, loops=loops)

    def play_loop(self, name: str, lane: int = 1) -> None:
        if name in self.looping_sounds:
            return
        sound = self.load_sound(name)
        if not sound:
            return
        channel = pygame.mixer.find_channel(True)
        if not channel:
            return
        left, right = self._pan_to_stereo(LANE_PAN.get(lane, 0.0))
        channel.set_volume(left * self.sfx_volume, right * self.sfx_volume)
        channel.play(sound, loops=-1)
        self.looping_sounds[name] = channel

    def stop_loop(self, name: str) -> None:
        channel = self.looping_sounds.pop(name, None)
        if channel:
            channel.stop()

    def update_loop_pan(self, name: str, lane: int, distance: float) -> None:
        channel = self.looping_sounds.get(name)
        if not channel:
            return
        left, right = self._pan_to_stereo(LANE_PAN.get(lane, 0.0))
        volume = self._distance_to_volume(distance) * self.sfx_volume
        channel.set_volume(left * volume, right * volume)

    def _pan_to_stereo(self, pan: float) -> Tuple[float, float]:
        pan = max(-1.0, min(1.0, pan))
        left = 1.0 if pan <= 0 else 1.0 - pan
        right = 1.0 if pan >= 0 else 1.0 + pan
        return left, right

    def _distance_to_volume(self, distance: float) -> float:
        distance = max(0.0, min(MAX_DISTANCE, distance))
        return 1.0 - (distance / MAX_DISTANCE)

    def play_music(self, name: str, loop: bool = True) -> None:
        path = self._resolve_path(name)
        if not path:
            print(f"Warning: music asset missing for {name}")
            return
        try:
            pygame.mixer.music.load(path)
            pygame.mixer.music.set_volume(self.music_volume)
            pygame.mixer.music.play(-1 if loop else 0)
        except pygame.error as exc:
            print(f"Warning: failed to load music {path}: {exc}")

    def stop_music(self) -> None:
        pygame.mixer.music.stop()

    def adjust_music_volume(self, delta: float) -> None:
        self.music_volume = max(0.0, min(1.0, self.music_volume + delta))
        pygame.mixer.music.set_volume(self.music_volume)
        self.tts.say(f"Music volume {int(self.music_volume * 100)} percent")


@dataclass
class Obstacle:
    lane: int
    distance: float
    kind: str
    height: str
    active: bool = True


@dataclass
class PowerUp:
    lane: int
    distance: float
    kind: str
    active: bool = True


@dataclass
class LetterCollectible:
    lane: int
    distance: float
    letter: str
    active: bool = True


class Player:
    def __init__(self) -> None:
        self.lane = 1
        self.jumping = False
        self.rolling = False
        self.jump_timer = 0.0
        self.roll_timer = 0.0
        self.super_sneakers = False
        self.jetpack = False
        self.hoverboard_active = False
        self.hoverboard_timer = 0.0

    def move_left(self) -> None:
        if self.lane > 0:
            self.lane -= 1

    def move_right(self) -> None:
        if self.lane < 2:
            self.lane += 1

    def jump(self, duration: float) -> None:
        self.jumping = True
        self.jump_timer = duration

    def roll(self, duration: float) -> None:
        self.rolling = True
        self.roll_timer = duration

    def update(self, dt: float) -> None:
        if self.jumping:
            self.jump_timer -= dt
            if self.jump_timer <= 0:
                self.jumping = False
        if self.rolling:
            self.roll_timer -= dt
            if self.roll_timer <= 0:
                self.rolling = False
        if self.hoverboard_active:
            self.hoverboard_timer -= dt
            if self.hoverboard_timer <= 0:
                self.hoverboard_active = False


class AchievementSystem:
    def __init__(self, tts: TTS, sound_manager: SoundManager) -> None:
        self.tts = tts
        self.sound_manager = sound_manager
        self.unlocked: Dict[str, bool] = {
            "High Jumper": False,
            "Gold Digger": False,
            "Marathon": False,
        }

    def check(self, stats: Dict[str, int]) -> Optional[str]:
        if not self.unlocked["High Jumper"] and stats["jumps"] >= 100:
            return self.unlock("High Jumper")
        if not self.unlocked["Gold Digger"] and stats["total_coins"] >= 5000:
            return self.unlock("Gold Digger")
        if not self.unlocked["Marathon"] and stats["score"] >= 100_000:
            return self.unlock("Marathon")
        return None

    def unlock(self, name: str) -> str:
        self.unlocked[name] = True
        self.sound_manager.play_sound("achievement_unlock", lane=1, distance=0)
        self.tts.say(f"Achievement unlocked: {name}")
        return name

    def list_status(self) -> List[str]:
        return [
            f"{name} - {'Unlocked' if status else 'Locked'}"
            for name, status in self.unlocked.items()
        ]


class Menu:
    def __init__(self, title: str, items: List[str], tts: TTS, sound_manager: SoundManager) -> None:
        self.title = title
        self.items = items
        self.tts = tts
        self.sound_manager = sound_manager
        self.index = 0
        self.tts.say(self.items[self.index])

    def move(self, direction: int) -> None:
        new_index = self.index + direction
        if new_index < 0 or new_index >= len(self.items):
            self.sound_manager.play_sound("menuedge")
            return
        self.index = new_index
        self.sound_manager.play_sound("menumove")
        self.tts.say(self.items[self.index])

    def jump_first(self) -> None:
        if self.index == 0:
            self.sound_manager.play_sound("menuedge")
            return
        self.index = 0
        self.sound_manager.play_sound("menumove")
        self.tts.say(self.items[self.index])

    def jump_last(self) -> None:
        if self.index == len(self.items) - 1:
            self.sound_manager.play_sound("menuedge")
            return
        self.index = len(self.items) - 1
        self.sound_manager.play_sound("menumove")
        self.tts.say(self.items[self.index])

    def jump_letter(self, letter: str) -> None:
        letter = letter.lower()
        for idx, item in enumerate(self.items):
            if item.lower().startswith(letter):
                self.index = idx
                self.sound_manager.play_sound("menumove")
                self.tts.say(self.items[self.index])
                return
        self.sound_manager.play_sound("menuedge")

    def select(self) -> str:
        self.sound_manager.play_sound("menuenter")
        return self.items[self.index]


class Economy:
    def __init__(self) -> None:
        self.coins = 0
        self.keys = 0
        self.mystery_boxes = 0
        self.powerup_durations: Dict[str, float] = {
            "jetpack": 10.0,
            "super_sneakers": 10.0,
            "magnet": 10.0,
            "multiplier": 10.0,
            "hoverboard": 30.0,
        }

    def buy_upgrade(self, powerup: str, cost: int) -> bool:
        if self.coins >= cost:
            self.coins -= cost
            self.powerup_durations[powerup] += 5.0
            return True
        return False

    def open_mystery_box(self) -> str:
        reward = random.choice(["Coins", "Keys", "Trophies"])
        return reward


class Game:
    def __init__(self) -> None:
        pygame.init()
        pygame.mixer.init()
        pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Blind Surfers")
        pygame.mixer.set_num_channels(32)

        self.clock = pygame.time.Clock()
        self.tts = TTS()
        self.sound_manager = SoundManager(self.tts)
        self.achievement_system = AchievementSystem(self.tts, self.sound_manager)
        self.economy = Economy()
        self.player = Player()

        self.running = True
        self.in_game = False
        self.game_over = False
        self.score = 0
        self.multiplier = 1
        self.speed = 25.0

        self.stats = {
            "jumps": 0,
            "total_coins": 0,
            "score": 0,
        }

        self.obstacles: List[Obstacle] = []
        self.powerups: List[PowerUp] = []
        self.letters: List[LetterCollectible] = []
        self.word_hunt = list("HUNT")
        self.word_progress: List[str] = []
        self.season_tokens = 0

        self.active_powerups: Dict[str, float] = {}

        self.main_menu = Menu(
            "Main Menu",
            [
                "Start Run",
                "Shop",
                "Achievements",
                "Quit",
            ],
            self.tts,
            self.sound_manager,
        )
        self.achievements_menu = Menu(
            "Achievements",
            self.achievement_system.list_status(),
            self.tts,
            self.sound_manager,
        )
        self.current_menu = self.main_menu
        self.sound_manager.play_music("theme.ogg")

    def reset_run(self) -> None:
        self.player = Player()
        self.score = 0
        self.multiplier = 1
        self.speed = 25.0
        self.stats["jumps"] = 0
        self.stats["score"] = 0
        self.obstacles.clear()
        self.powerups.clear()
        self.letters.clear()
        self.word_progress.clear()
        self.active_powerups.clear()
        self.game_over = False
        self.in_game = True
        self.tts.say("Run started")

    def spawn_obstacle(self) -> None:
        lane = random.choice(LANES)
        height = random.choice(["low", "high"])
        kind = random.choice(["barrier", "train"])
        distance = MAX_DISTANCE
        self.obstacles.append(Obstacle(lane=lane, distance=distance, kind=kind, height=height))
        if kind == "barrier":
            if height == "low":
                self.sound_manager.play_sound("barrier_low", lane=lane, distance=distance)
            else:
                self.sound_manager.play_sound("barrier_high", lane=lane, distance=distance)
        else:
            self.sound_manager.play_sound("train_rumble", lane=1, distance=distance)

    def spawn_powerup(self) -> None:
        lane = random.choice(LANES)
        kind = random.choice(["jetpack", "super_sneakers", "magnet", "multiplier", "hoverboard"])
        self.powerups.append(PowerUp(lane=lane, distance=MAX_DISTANCE, kind=kind))
        self.sound_manager.play_sound("powerup_spawn", lane=lane, distance=MAX_DISTANCE)

    def spawn_letter(self) -> None:
        if not self.word_hunt:
            return
        letter = self.word_hunt[len(self.word_progress) % len(self.word_hunt)]
        lane = random.choice(LANES)
        self.letters.append(LetterCollectible(lane=lane, distance=MAX_DISTANCE, letter=letter))
        self.sound_manager.play_sound("letter_spawn", lane=lane, distance=MAX_DISTANCE)

    def spawn_season_token(self) -> None:
        lane = random.choice(LANES)
        self.powerups.append(PowerUp(lane=lane, distance=MAX_DISTANCE, kind="season_token"))
        self.sound_manager.play_sound("season_token", lane=lane, distance=MAX_DISTANCE)

    def handle_collision(self, obstacle: Obstacle) -> None:
        if self.player.jetpack:
            return
        if self.player.hoverboard_active:
            self.player.hoverboard_active = False
            self.sound_manager.play_sound("hoverboard_break", lane=obstacle.lane, distance=0)
            return
        self.game_over = True
        self.in_game = False
        self.sound_manager.play_sound("crash", lane=obstacle.lane, distance=0)
        self.sound_manager.stop_music()
        self.tts.say(f"Game Over. Score: {self.score}")

    def activate_powerup(self, powerup: PowerUp) -> None:
        duration = self.economy.powerup_durations.get(powerup.kind, 10.0)
        if powerup.kind == "jetpack":
            self.player.jetpack = True
            self.active_powerups["jetpack"] = duration
            self.sound_manager.play_loop("jetpack_loop", lane=1)
        elif powerup.kind == "super_sneakers":
            self.player.super_sneakers = True
            self.active_powerups["super_sneakers"] = duration
        elif powerup.kind == "magnet":
            self.active_powerups["magnet"] = duration
            self.sound_manager.play_loop("magnet_loop", lane=1)
        elif powerup.kind == "multiplier":
            self.multiplier = 2
            self.active_powerups["multiplier"] = duration
            self.sound_manager.play_sound("multiplier_on", lane=1, distance=0)
        elif powerup.kind == "hoverboard":
            self.player.hoverboard_active = True
            self.player.hoverboard_timer = duration
            self.sound_manager.play_sound("hoverboard_on", lane=1, distance=0)
        elif powerup.kind == "season_token":
            self.season_tokens += 1
            self.tts.say("Season token collected")
        self.sound_manager.play_sound("powerup_collect", lane=powerup.lane, distance=0)

    def update_powerups(self, dt: float) -> None:
        expired = []
        for kind in list(self.active_powerups.keys()):
            self.active_powerups[kind] -= dt
            if self.active_powerups[kind] <= 0:
                expired.append(kind)
        for kind in expired:
            del self.active_powerups[kind]
            if kind == "jetpack":
                self.player.jetpack = False
                self.sound_manager.stop_loop("jetpack_loop")
            elif kind == "super_sneakers":
                self.player.super_sneakers = False
            elif kind == "magnet":
                self.sound_manager.stop_loop("magnet_loop")
            elif kind == "multiplier":
                self.multiplier = 1

    def update_obstacles(self, dt: float) -> None:
        for obstacle in self.obstacles:
            if not obstacle.active:
                continue
            obstacle.distance -= self.speed * dt
            if obstacle.kind == "barrier":
                sound_name = "barrier_low" if obstacle.height == "low" else "barrier_high"
                self.sound_manager.play_sound(sound_name, lane=obstacle.lane, distance=obstacle.distance)
            else:
                self.sound_manager.play_sound("train_rumble", lane=1, distance=obstacle.distance)
                pan_lane = 0 if obstacle.lane == 0 else 2
                self.sound_manager.play_sound("train_honk", lane=pan_lane, distance=obstacle.distance)
            if obstacle.distance <= 0:
                obstacle.active = False
                if obstacle.lane == self.player.lane:
                    if obstacle.height == "low" and self.player.jumping:
                        continue
                    if obstacle.height == "high" and self.player.rolling:
                        continue
                    self.handle_collision(obstacle)
        self.obstacles = [o for o in self.obstacles if o.active]

    def update_powerup_objects(self, dt: float) -> None:
        for powerup in self.powerups:
            if not powerup.active:
                continue
            powerup.distance -= self.speed * dt
            if powerup.distance <= 0:
                powerup.active = False
                if powerup.lane == self.player.lane:
                    self.activate_powerup(powerup)
        self.powerups = [p for p in self.powerups if p.active]

    def update_letters(self, dt: float) -> None:
        for letter in self.letters:
            if not letter.active:
                continue
            letter.distance -= self.speed * dt
            if letter.distance <= 0:
                letter.active = False
                if letter.lane == self.player.lane:
                    self.word_progress.append(letter.letter)
                    self.tts.say(f"You collected {letter.letter}!")
                    if self.word_progress == self.word_hunt:
                        self.tts.say("Word hunt complete")
                        self.economy.coins += 500
                        self.word_progress.clear()
        self.letters = [l for l in self.letters if l.active]

    def update_score(self, dt: float) -> None:
        self.score += int(10 * self.multiplier * dt * 60)
        self.stats["score"] = self.score

    def collect_coin(self, lane: int) -> None:
        self.economy.coins += 1
        self.stats["total_coins"] += 1
        self.sound_manager.play_sound("coin_collect", lane=lane, distance=0)

    def handle_input(self, event: pygame.event.Event) -> None:
        if event.type != pygame.KEYDOWN:
            return
        if event.key == pygame.K_PAGEUP:
            self.sound_manager.adjust_music_volume(0.05)
        if event.key == pygame.K_PAGEDOWN:
            self.sound_manager.adjust_music_volume(-0.05)
        if not self.in_game:
            if event.key == pygame.K_UP:
                self.current_menu.move(-1)
            elif event.key == pygame.K_DOWN:
                self.current_menu.move(1)
            elif event.key == pygame.K_HOME:
                self.current_menu.jump_first()
            elif event.key == pygame.K_END:
                self.current_menu.jump_last()
            elif event.key == pygame.K_RETURN:
                selection = self.current_menu.select()
                self.handle_menu_select(selection)
            elif event.key == pygame.K_ESCAPE:
                self.sound_manager.play_sound("menuclose")
                if self.current_menu is self.achievements_menu:
                    self.current_menu = self.main_menu
                    self.sound_manager.play_music("theme.ogg")
            elif pygame.K_a <= event.key <= pygame.K_z:
                self.current_menu.jump_letter(chr(event.key))
            return

        if event.key == pygame.K_LEFT:
            self.player.move_left()
            self.sound_manager.play_sound("swoosh", lane=self.player.lane, distance=0)
        elif event.key == pygame.K_RIGHT:
            self.player.move_right()
            self.sound_manager.play_sound("swoosh", lane=self.player.lane, distance=0)
        elif event.key == pygame.K_UP:
            jump_duration = 0.7 if not self.player.super_sneakers else 1.0
            self.player.jump(jump_duration)
            self.stats["jumps"] += 1
            sound = "super_jump" if self.player.super_sneakers else "jump"
            self.sound_manager.play_sound(sound, lane=self.player.lane, distance=0)
        elif event.key == pygame.K_DOWN:
            self.player.roll(0.7)
            self.sound_manager.play_sound("roll", lane=self.player.lane, distance=0)

    def handle_menu_select(self, selection: str) -> None:
        if selection == "Start Run":
            self.reset_run()
            self.sound_manager.stop_music()
        elif selection == "Shop":
            self.tts.say("Shop is available in this build. Buy upgrades with coins.")
        elif selection == "Achievements":
            self.achievements_menu = Menu(
                "Achievements",
                self.achievement_system.list_status(),
                self.tts,
                self.sound_manager,
            )
            self.current_menu = self.achievements_menu
            self.sound_manager.play_music("achmusic.ogg")
        elif selection == "Quit":
            self.running = False

    def update(self, dt: float) -> None:
        if not self.in_game:
            return
        self.player.update(dt)
        self.update_powerups(dt)
        self.update_obstacles(dt)
        self.update_powerup_objects(dt)
        self.update_letters(dt)
        self.update_score(dt)

        if random.random() < 0.02:
            self.spawn_obstacle()
        if random.random() < 0.01:
            self.spawn_powerup()
        if random.random() < 0.008:
            self.spawn_letter()
        if random.random() < 0.005:
            self.spawn_season_token()

        if "magnet" in self.active_powerups:
            self.collect_coin(self.player.lane)

        unlocked = self.achievement_system.check(self.stats)
        if unlocked:
            time.sleep(0.5)

    def run(self) -> None:
        self.tts.say("Blind Surfers")
        while self.running:
            dt = self.clock.tick(FPS) / 1000.0
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                    break
                self.handle_input(event)
            self.update(dt)
        pygame.quit()
        sys.exit()


if __name__ == "__main__":
    Game().run()
