from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Obstacle:
    lane: int
    distance: float
    kind: str
    height: str
    active: bool = True
    sound_tag: str | None = None
    honk_played: bool = False


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


@dataclass
class CoinCollectible:
    lane: int
    distance: float
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

    def update(self, delta_seconds: float) -> None:
        if self.jumping:
            self.jump_timer -= delta_seconds
            if self.jump_timer <= 0:
                self.jumping = False
        if self.rolling:
            self.roll_timer -= delta_seconds
            if self.roll_timer <= 0:
                self.rolling = False
        if self.hoverboard_active:
            self.hoverboard_timer -= delta_seconds
            if self.hoverboard_timer <= 0:
                self.hoverboard_active = False
