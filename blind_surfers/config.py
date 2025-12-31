from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict


@dataclass(frozen=True)
class GameConfig:
    screen_width: int = 800
    screen_height: int = 600
    fps: int = 60
    max_distance: float = 100.0
    lanes: tuple[int, int, int] = (0, 1, 2)
    lane_pan: Dict[int, float] = field(default_factory=lambda: {0: -0.8, 1: 0.0, 2: 0.8})


@dataclass(frozen=True)
class EconomyConfig:
    powerup_base_duration: Dict[str, float] = field(
        default_factory=lambda: {
            "jetpack": 10.0,
            "super_sneakers": 10.0,
            "magnet": 10.0,
            "multiplier": 10.0,
            "hoverboard": 30.0,
        }
    )
    upgrade_costs: Dict[str, int] = field(
        default_factory=lambda: {
            "jetpack": 500,
            "super_sneakers": 400,
            "magnet": 450,
            "multiplier": 600,
            "hoverboard": 700,
        }
    )
    mystery_box_cost: int = 300


@dataclass(frozen=True)
class SpawnConfig:
    obstacle_rate: float = 0.02
    powerup_rate: float = 0.01
    letter_rate: float = 0.008
    season_token_rate: float = 0.005
    coin_rate: float = 0.05


@dataclass(frozen=True)
class AudioConfig:
    sound_dir_name: str = "sounds"
    default_music_volume: float = 0.8
    default_sfx_volume: float = 0.9
    mixer_channels: int = 32


@dataclass(frozen=True)
class GameplayConfig:
    base_speed: float = 25.0
    jump_duration: float = 0.7
    super_jump_duration: float = 1.0
    roll_duration: float = 0.7
    score_rate: int = 10
    achievement_pause_seconds: float = 0.5
    word_hunt_letters: tuple[str, ...] = ("H", "U", "N", "T")


@dataclass(frozen=True)
class AppConfig:
    game: GameConfig = field(default_factory=GameConfig)
    economy: EconomyConfig = field(default_factory=EconomyConfig)
    spawn: SpawnConfig = field(default_factory=SpawnConfig)
    audio: AudioConfig = field(default_factory=AudioConfig)
    gameplay: GameplayConfig = field(default_factory=GameplayConfig)
