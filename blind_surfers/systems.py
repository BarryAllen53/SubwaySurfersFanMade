from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Dict, List

from blind_surfers.audio import SoundManager, TTS
from blind_surfers.config import AppConfig


class AchievementSystem:
    def __init__(self, tts: TTS, sound_manager: SoundManager) -> None:
        self.tts = tts
        self.sound_manager = sound_manager
        self.unlocked: Dict[str, bool] = {
            "High Jumper": False,
            "Gold Digger": False,
            "Marathon": False,
        }

    def check(self, stats: Dict[str, int]) -> str | None:
        if not self.unlocked["High Jumper"] and stats["jumps"] >= 100:
            return self.unlock("High Jumper")
        if not self.unlocked["Gold Digger"] and stats["total_coins"] >= 5000:
            return self.unlock("Gold Digger")
        if not self.unlocked["Marathon"] and stats["score"] >= 100_000:
            return self.unlock("Marathon")
        return None

    def unlock(self, name: str) -> str:
        self.unlocked[name] = True
        self.sound_manager.play_sound("achievement_unlock", lane=1, distance=0.0)
        self.tts.say(f"Achievement unlocked: {name}")
        return name

    def list_status(self) -> List[str]:
        return [
            f"{name} - {'Unlocked' if status else 'Locked'}"
            for name, status in self.unlocked.items()
        ]


@dataclass
class Economy:
    config: AppConfig
    coins: int = 0
    keys: int = 0
    mystery_boxes: int = 0
    powerup_durations: Dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.powerup_durations = dict(self.config.economy.powerup_base_duration)

    def buy_upgrade(self, powerup: str) -> bool:
        cost = self.config.economy.upgrade_costs.get(powerup, 0)
        if self.coins >= cost and cost > 0:
            self.coins -= cost
            self.powerup_durations[powerup] = self.powerup_durations.get(powerup, 10.0) + 5.0
            return True
        return False

    def buy_mystery_box(self) -> bool:
        if self.coins >= self.config.economy.mystery_box_cost:
            self.coins -= self.config.economy.mystery_box_cost
            self.mystery_boxes += 1
            return True
        return False

    def open_mystery_box(self) -> str:
        if self.mystery_boxes <= 0:
            return "None"
        self.mystery_boxes -= 1
        reward = random.choice(["Coins", "Keys", "Trophies"])
        if reward == "Coins":
            self.coins += 500
        elif reward == "Keys":
            self.keys += 1
        return reward


@dataclass
class WordHunt:
    letters: tuple[str, ...]
    collected: List[str] = field(default_factory=list)

    def next_letter(self) -> str:
        if not self.letters:
            return ""
        return self.letters[len(self.collected) % len(self.letters)]

    def collect(self, letter: str) -> bool:
        self.collected.append(letter)
        if len(self.collected) == len(self.letters):
            self.collected.clear()
            return True
        return False


@dataclass
class SeasonHunt:
    tokens: int = 0

    def collect(self) -> None:
        self.tokens += 1
