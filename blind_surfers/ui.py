from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List

import pygame

from blind_surfers.audio import SoundManager, TTS


@dataclass
class MenuItem:
    label: str
    action: str


class Menu:
    def __init__(self, title: str, items: List[MenuItem], tts: TTS, sound_manager: SoundManager) -> None:
        self.title = title
        self.items = items
        self.tts = tts
        self.sound_manager = sound_manager
        self.index = 0
        if self.items:
            self.tts.say(self.items[self.index].label)

    def move(self, direction: int) -> None:
        new_index = self.index + direction
        if new_index < 0 or new_index >= len(self.items):
            self.sound_manager.play_sound("menuedge")
            return
        self.index = new_index
        self.sound_manager.play_sound("menumove")
        self.tts.say(self.items[self.index].label)

    def jump_first(self) -> None:
        if self.index == 0:
            self.sound_manager.play_sound("menuedge")
            return
        self.index = 0
        self.sound_manager.play_sound("menumove")
        self.tts.say(self.items[self.index].label)

    def jump_last(self) -> None:
        if self.index == len(self.items) - 1:
            self.sound_manager.play_sound("menuedge")
            return
        self.index = len(self.items) - 1
        self.sound_manager.play_sound("menumove")
        self.tts.say(self.items[self.index].label)

    def jump_letter(self, letter: str) -> None:
        letter = letter.lower()
        for idx, item in enumerate(self.items):
            if item.label.lower().startswith(letter):
                self.index = idx
                self.sound_manager.play_sound("menumove")
                self.tts.say(self.items[self.index].label)
                return
        self.sound_manager.play_sound("menuedge")

    def select(self) -> MenuItem:
        self.sound_manager.play_sound("menuenter")
        return self.items[self.index]


class MenuController:
    def __init__(self, tts: TTS, sound_manager: SoundManager) -> None:
        self.tts = tts
        self.sound_manager = sound_manager
        self.active_menu: Menu | None = None
        self.on_close: Callable[[], None] | None = None

    def open_menu(self, menu: Menu, on_close: Callable[[], None] | None = None) -> None:
        self.active_menu = menu
        self.on_close = on_close
        self.sound_manager.play_sound("menuopen")

    def close_menu(self) -> None:
        self.sound_manager.play_sound("menuclose")
        if self.on_close:
            self.on_close()
        self.active_menu = None
        self.on_close = None

    def handle_input(self, event: pygame.event.Event) -> str | None:
        if not self.active_menu:
            return None
        if event.type != pygame.KEYDOWN:
            return None
        if event.key == pygame.K_UP:
            self.active_menu.move(-1)
        elif event.key == pygame.K_DOWN:
            self.active_menu.move(1)
        elif event.key == pygame.K_HOME:
            self.active_menu.jump_first()
        elif event.key == pygame.K_END:
            self.active_menu.jump_last()
        elif event.key == pygame.K_RETURN:
            item = self.active_menu.select()
            return item.action
        elif event.key == pygame.K_ESCAPE:
            self.close_menu()
        elif pygame.K_a <= event.key <= pygame.K_z:
            self.active_menu.jump_letter(chr(event.key))
        return None
