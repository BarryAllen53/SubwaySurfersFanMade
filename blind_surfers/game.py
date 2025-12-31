from __future__ import annotations

import random
import sys
import time
from enum import Enum

import pygame

from blind_surfers.audio import SoundManager, TTS
from blind_surfers.config import AppConfig
from blind_surfers.models import CoinCollectible, LetterCollectible, Obstacle, Player, PowerUp
from blind_surfers.systems import AchievementSystem, Economy, SeasonHunt, WordHunt
from blind_surfers.ui import Menu, MenuController, MenuItem


class GameState(Enum):
    MENU = "menu"
    RUNNING = "running"
    GAME_OVER = "game_over"


class Game:
    def __init__(self) -> None:
        self.config = AppConfig()
        self.tts = TTS()
        self.audio_ready = False
        self.display_ready = False
        try:
            pygame.init()
            self.display_ready = True
        except pygame.error as exc:
            print(f"Display warning: {exc}")
        try:
            pygame.mixer.init()
            pygame.mixer.set_num_channels(self.config.audio.mixer_channels)
            self.audio_ready = True
        except pygame.error as exc:
            print(f"Audio warning: {exc}")
        if self.display_ready:
            try:
                pygame.display.set_mode((self.config.game.screen_width, self.config.game.screen_height))
                pygame.display.set_caption("Blind Surfers")
            except pygame.error as exc:
                print(f"Display setup warning: {exc}")
        self.clock = pygame.time.Clock()
        self.sound_manager = SoundManager(self.config, self.tts)
        self.achievement_system = AchievementSystem(self.tts, self.sound_manager)
        self.economy = Economy(self.config)
        self.word_hunt = WordHunt(self.config.gameplay.word_hunt_letters)
        self.season_hunt = SeasonHunt()
        self.player = Player()
        self.running = True
        self.state = GameState.MENU
        self.score = 0
        self.multiplier = 1
        self.speed = self.config.gameplay.base_speed
        self.stats = {"jumps": 0, "total_coins": 0, "score": 0}
        self.obstacles: list[Obstacle] = []
        self.powerups: list[PowerUp] = []
        self.letters: list[LetterCollectible] = []
        self.coins: list[CoinCollectible] = []
        self.active_powerups: dict[str, float] = {}
        self.obstacle_id = 0
        self.menu_controller = MenuController(self.tts, self.sound_manager)
        self.main_menu = self.build_main_menu()
        self.menu_controller.open_menu(self.main_menu)
        self.sound_manager.play_music("theme.ogg")

    def build_main_menu(self) -> Menu:
        items = [
            MenuItem("Start Run", "start_run"),
            MenuItem("Shop", "shop"),
            MenuItem("Achievements", "achievements"),
            MenuItem("Quit", "quit"),
        ]
        return Menu("Main Menu", items, self.tts, self.sound_manager)

    def build_shop_menu(self) -> Menu:
        items = [
            MenuItem("Upgrade Jetpack Duration", "upgrade_jetpack"),
            MenuItem("Upgrade Super Sneakers Duration", "upgrade_super_sneakers"),
            MenuItem("Upgrade Coin Magnet Duration", "upgrade_magnet"),
            MenuItem("Upgrade Multiplier Duration", "upgrade_multiplier"),
            MenuItem("Upgrade Hoverboard Duration", "upgrade_hoverboard"),
            MenuItem("Buy Mystery Box", "buy_mystery_box"),
            MenuItem("Open Mystery Box", "open_mystery_box"),
            MenuItem("Back", "back"),
        ]
        return Menu("Shop", items, self.tts, self.sound_manager)

    def build_achievements_menu(self) -> Menu:
        items = [MenuItem(label, "none") for label in self.achievement_system.list_status()]
        items.append(MenuItem("Back", "back"))
        return Menu("Achievements", items, self.tts, self.sound_manager)

    def reset_run(self) -> None:
        self.player = Player()
        self.score = 0
        self.multiplier = 1
        self.speed = self.config.gameplay.base_speed
        self.stats["jumps"] = 0
        self.stats["score"] = 0
        self.obstacles.clear()
        self.powerups.clear()
        self.letters.clear()
        self.coins.clear()
        self.active_powerups.clear()
        self.state = GameState.RUNNING
        self.tts.say("Run started")

    def spawn_obstacle(self) -> None:
        lane = random.choice(self.config.game.lanes)
        height = random.choice(["low", "high"])
        kind = random.choice(["barrier", "train"])
        distance = self.config.game.max_distance
        self.obstacle_id += 1
        tag = f"obstacle_{self.obstacle_id}"
        obstacle = Obstacle(lane=lane, distance=distance, kind=kind, height=height, sound_tag=tag)
        self.obstacles.append(obstacle)
        if kind == "barrier":
            sound_name = "barrier_low" if height == "low" else "barrier_high"
            self.sound_manager.start_loop(tag, sound_name, lane, distance)
        else:
            self.sound_manager.start_loop(tag, "train_rumble", 1, distance)

    def spawn_powerup(self) -> None:
        lane = random.choice(self.config.game.lanes)
        kind = random.choice(["jetpack", "super_sneakers", "magnet", "multiplier", "hoverboard"])
        self.powerups.append(PowerUp(lane=lane, distance=self.config.game.max_distance, kind=kind))
        self.sound_manager.play_sound("powerup_spawn", lane=lane, distance=self.config.game.max_distance)

    def spawn_letter(self) -> None:
        letter = self.word_hunt.next_letter()
        if not letter:
            return
        lane = random.choice(self.config.game.lanes)
        self.letters.append(
            LetterCollectible(lane=lane, distance=self.config.game.max_distance, letter=letter)
        )
        self.sound_manager.play_sound("letter_spawn", lane=lane, distance=self.config.game.max_distance)

    def spawn_coin(self) -> None:
        lane = random.choice(self.config.game.lanes)
        self.coins.append(CoinCollectible(lane=lane, distance=self.config.game.max_distance))
        self.sound_manager.play_sound("coin_spawn", lane=lane, distance=self.config.game.max_distance)

    def spawn_season_token(self) -> None:
        lane = random.choice(self.config.game.lanes)
        self.powerups.append(PowerUp(lane=lane, distance=self.config.game.max_distance, kind="season_token"))
        self.sound_manager.play_sound("season_token", lane=lane, distance=self.config.game.max_distance)

    def handle_collision(self, obstacle: Obstacle) -> None:
        if self.player.jetpack:
            return
        if self.player.hoverboard_active:
            self.player.hoverboard_active = False
            self.sound_manager.play_sound("hoverboard_break", lane=obstacle.lane, distance=0.0)
            return
        self.state = GameState.GAME_OVER
        self.sound_manager.play_sound("crash", lane=obstacle.lane, distance=0.0)
        self.sound_manager.stop_music()
        self.tts.say(f"Game Over. Score: {self.score}")
        if self.economy.keys > 0:
            self.tts.say("Press K to use a key and continue")

    def activate_powerup(self, powerup: PowerUp) -> None:
        duration = self.economy.powerup_durations.get(powerup.kind, 10.0)
        if powerup.kind == "jetpack":
            self.player.jetpack = True
            self.active_powerups["jetpack"] = duration
            self.sound_manager.start_loop("jetpack", "jetpack_loop", 1, 0.0)
        elif powerup.kind == "super_sneakers":
            self.player.super_sneakers = True
            self.active_powerups["super_sneakers"] = duration
        elif powerup.kind == "magnet":
            self.active_powerups["magnet"] = duration
            self.sound_manager.start_loop("magnet", "magnet_loop", 1, 0.0)
        elif powerup.kind == "multiplier":
            self.multiplier = 2
            self.active_powerups["multiplier"] = duration
            self.sound_manager.play_sound("multiplier_on", lane=1, distance=0.0)
        elif powerup.kind == "hoverboard":
            self.player.hoverboard_active = True
            self.player.hoverboard_timer = duration
            self.sound_manager.play_sound("hoverboard_on", lane=1, distance=0.0)
        elif powerup.kind == "season_token":
            self.season_hunt.collect()
            self.tts.say("Season token collected")
        self.sound_manager.play_sound("powerup_collect", lane=powerup.lane, distance=0.0)

    def update_powerups(self, delta_seconds: float) -> None:
        expired = []
        for kind, remaining in self.active_powerups.items():
            self.active_powerups[kind] = remaining - delta_seconds
            if self.active_powerups[kind] <= 0:
                expired.append(kind)
        for kind in expired:
            del self.active_powerups[kind]
            if kind == "jetpack":
                self.player.jetpack = False
                self.sound_manager.stop_loop("jetpack")
            elif kind == "super_sneakers":
                self.player.super_sneakers = False
            elif kind == "magnet":
                self.sound_manager.stop_loop("magnet")
            elif kind == "multiplier":
                self.multiplier = 1

    def update_obstacles(self, delta_seconds: float) -> None:
        for obstacle in self.obstacles:
            if not obstacle.active:
                continue
            obstacle.distance -= self.speed * delta_seconds
            if obstacle.sound_tag:
                if obstacle.kind == "train":
                    pan = self.config.game.lane_pan.get(obstacle.lane, 0.0)
                    progress = 1.0 - (obstacle.distance / self.config.game.max_distance)
                    self.sound_manager.update_loop_with_pan(obstacle.sound_tag, pan * progress, obstacle.distance)
                    if obstacle.distance <= 20 and not obstacle.honk_played:
                        obstacle.honk_played = True
                        self.sound_manager.play_sound("train_honk", lane=obstacle.lane, distance=obstacle.distance)
                else:
                    self.sound_manager.update_loop(obstacle.sound_tag, obstacle.lane, obstacle.distance)
            if obstacle.distance <= 0:
                obstacle.active = False
                if obstacle.sound_tag:
                    self.sound_manager.stop_loop(obstacle.sound_tag)
                if obstacle.lane == self.player.lane:
                    if obstacle.height == "low" and self.player.jumping:
                        continue
                    if obstacle.height == "high" and self.player.rolling:
                        continue
                    self.handle_collision(obstacle)
        self.obstacles = [o for o in self.obstacles if o.active]

    def update_powerup_objects(self, delta_seconds: float) -> None:
        for powerup in self.powerups:
            if not powerup.active:
                continue
            powerup.distance -= self.speed * delta_seconds
            if powerup.distance <= 0:
                powerup.active = False
                if powerup.lane == self.player.lane:
                    self.activate_powerup(powerup)
        self.powerups = [p for p in self.powerups if p.active]

    def update_letters(self, delta_seconds: float) -> None:
        for letter in self.letters:
            if not letter.active:
                continue
            letter.distance -= self.speed * delta_seconds
            if letter.distance <= 0:
                letter.active = False
                if letter.lane == self.player.lane:
                    completed = self.word_hunt.collect(letter.letter)
                    self.tts.say(f"You collected {letter.letter}!")
                    if completed:
                        self.tts.say("Word hunt complete")
                        self.economy.coins += 500
        self.letters = [l for l in self.letters if l.active]

    def update_coins(self, delta_seconds: float) -> None:
        for coin in self.coins:
            if not coin.active:
                continue
            coin.distance -= self.speed * delta_seconds
            if coin.distance <= 0:
                coin.active = False
                if coin.lane == self.player.lane or "magnet" in self.active_powerups:
                    self.collect_coin(coin.lane)
        self.coins = [c for c in self.coins if c.active]

    def update_score(self, delta_seconds: float) -> None:
        self.score += int(self.config.gameplay.score_rate * self.multiplier * delta_seconds * 60)
        self.stats["score"] = self.score

    def collect_coin(self, lane: int) -> None:
        self.economy.coins += 1
        self.stats["total_coins"] += 1
        self.sound_manager.play_sound("coin_collect", lane=lane, distance=0.0)

    def continue_run_with_key(self) -> None:
        if self.economy.keys <= 0:
            return
        self.economy.keys -= 1
        self.state = GameState.RUNNING
        self.player.hoverboard_active = True
        self.player.hoverboard_timer = 3.0
        self.sound_manager.play_sound("hoverboard_on", lane=1, distance=0.0)
        self.tts.say("Continuing run")

    def handle_menu_action(self, action: str) -> None:
        match action:
            case "start_run":
                self.reset_run()
                self.menu_controller.active_menu = None
                self.sound_manager.stop_music()
            case "shop":
                self.menu_controller.open_menu(self.build_shop_menu(), on_close=self.return_to_main_menu)
            case "achievements":
                self.sound_manager.play_music("achmusic.ogg")
                self.menu_controller.open_menu(self.build_achievements_menu(), on_close=self.return_to_main_menu)
            case "quit":
                self.running = False
            case "upgrade_jetpack":
                self.handle_upgrade("jetpack")
            case "upgrade_super_sneakers":
                self.handle_upgrade("super_sneakers")
            case "upgrade_magnet":
                self.handle_upgrade("magnet")
            case "upgrade_multiplier":
                self.handle_upgrade("multiplier")
            case "upgrade_hoverboard":
                self.handle_upgrade("hoverboard")
            case "buy_mystery_box":
                if self.economy.buy_mystery_box():
                    self.tts.say("Mystery box purchased")
                else:
                    self.tts.say("Not enough coins")
            case "open_mystery_box":
                if self.economy.mystery_boxes <= 0:
                    self.tts.say("No mystery boxes available")
                else:
                    self.sound_manager.play_sound("mystery_roll", lane=1, distance=0.0)
                    reward = self.economy.open_mystery_box()
                    self.tts.say(f"You won {reward}")
            case "back":
                self.return_to_main_menu()
            case "none":
                self.tts.say("Achievement status listed")
            case _:
                return

    def handle_upgrade(self, powerup: str) -> None:
        if self.economy.buy_upgrade(powerup):
            self.tts.say("Upgrade purchased")
        else:
            self.tts.say("Not enough coins")

    def return_to_main_menu(self) -> None:
        self.menu_controller.open_menu(self.build_main_menu())
        self.sound_manager.play_music("theme.ogg")

    def handle_input(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_PAGEUP:
                self.sound_manager.adjust_music_volume(0.05)
                return
            if event.key == pygame.K_PAGEDOWN:
                self.sound_manager.adjust_music_volume(-0.05)
                return
        if self.state == GameState.MENU:
            action = self.menu_controller.handle_input(event)
            if action:
                self.handle_menu_action(action)
            return
        if self.state == GameState.GAME_OVER:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_k:
                    self.continue_run_with_key()
                elif event.key == pygame.K_ESCAPE:
                    self.state = GameState.MENU
                    self.return_to_main_menu()
            return
        if event.type != pygame.KEYDOWN:
            return
        if event.key == pygame.K_LEFT:
            self.player.move_left()
            self.sound_manager.play_sound("swoosh", lane=self.player.lane, distance=0.0)
        elif event.key == pygame.K_RIGHT:
            self.player.move_right()
            self.sound_manager.play_sound("swoosh", lane=self.player.lane, distance=0.0)
        elif event.key == pygame.K_UP:
            jump_duration = (
                self.config.gameplay.super_jump_duration
                if self.player.super_sneakers
                else self.config.gameplay.jump_duration
            )
            self.player.jump(jump_duration)
            self.stats["jumps"] += 1
            sound = "super_jump" if self.player.super_sneakers else "jump"
            self.sound_manager.play_sound(sound, lane=self.player.lane, distance=0.0)
        elif event.key == pygame.K_DOWN:
            self.player.roll(self.config.gameplay.roll_duration)
            self.sound_manager.play_sound("roll", lane=self.player.lane, distance=0.0)

    def update(self, delta_seconds: float) -> None:
        if self.state != GameState.RUNNING:
            return
        self.player.update(delta_seconds)
        self.update_powerups(delta_seconds)
        self.update_obstacles(delta_seconds)
        self.update_powerup_objects(delta_seconds)
        self.update_letters(delta_seconds)
        self.update_coins(delta_seconds)
        self.update_score(delta_seconds)
        if random.random() < self.config.spawn.obstacle_rate:
            self.spawn_obstacle()
        if random.random() < self.config.spawn.powerup_rate:
            self.spawn_powerup()
        if random.random() < self.config.spawn.letter_rate:
            self.spawn_letter()
        if random.random() < self.config.spawn.season_token_rate:
            self.spawn_season_token()
        if random.random() < self.config.spawn.coin_rate:
            self.spawn_coin()
        unlocked = self.achievement_system.check(self.stats)
        if unlocked:
            time.sleep(self.config.gameplay.achievement_pause_seconds)

    def run(self) -> None:
        self.tts.say("Blind Surfers")
        while self.running:
            delta_seconds = self.clock.tick(self.config.game.fps) / 1000.0
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                    break
                self.handle_input(event)
            self.update(delta_seconds)
        pygame.quit()
        sys.exit()
