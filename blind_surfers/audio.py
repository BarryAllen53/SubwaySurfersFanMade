from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import pygame
from accessible_output2 import outputs

from blind_surfers.config import AppConfig


@dataclass
class SoundInstance:
    name: str
    channel: pygame.mixer.Channel
    lane: int
    distance: float


class TTS:
    def __init__(self) -> None:
        self.speaker = outputs.auto.Auto()

    def say(self, text: str) -> None:
        try:
            self.speaker.speak(text)
        except Exception as exc:
            print(f"TTS warning: {exc}")


class SoundManager:
    def __init__(self, config: AppConfig, tts: TTS) -> None:
        self.config = config
        self.tts = tts
        self.sounds: Dict[str, pygame.mixer.Sound] = {}
        self.looping_instances: Dict[str, SoundInstance] = {}
        self.music_volume = config.audio.default_music_volume
        self.sfx_volume = config.audio.default_sfx_volume
        self.sound_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), config.audio.sound_dir_name)

    def _resolve_path(self, name: str) -> Optional[str]:
        if os.path.splitext(name)[1]:
            path = os.path.join(self.sound_dir, name)
            return path if os.path.exists(path) else None
        for ext in (".ogg", ".wav", ".mp3"):
            path = os.path.join(self.sound_dir, f"{name}{ext}")
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

    def _pan_to_stereo(self, pan: float) -> Tuple[float, float]:
        pan = max(-1.0, min(1.0, pan))
        left = 1.0 - max(0.0, pan)
        right = 1.0 + min(0.0, pan)
        return max(0.0, min(1.0, left)), max(0.0, min(1.0, right))

    def _distance_to_volume(self, distance: float) -> float:
        distance = max(0.0, min(self.config.game.max_distance, distance))
        return max(0.0, 1.0 - (distance / self.config.game.max_distance))

    def play_sound(self, name: str, lane: int = 1, distance: float = 0.0, loops: int = 0) -> None:
        sound = self.load_sound(name)
        if not sound:
            return
        channel = pygame.mixer.find_channel(True)
        if not channel:
            return
        left, right = self._pan_to_stereo(self.config.game.lane_pan.get(lane, 0.0))
        volume = self._distance_to_volume(distance) * self.sfx_volume
        channel.set_volume(left * volume, right * volume)
        channel.play(sound, loops=loops)

    def start_loop(self, tag: str, name: str, lane: int, distance: float) -> None:
        if tag in self.looping_instances:
            return
        sound = self.load_sound(name)
        if not sound:
            return
        channel = pygame.mixer.find_channel(True)
        if not channel:
            return
        left, right = self._pan_to_stereo(self.config.game.lane_pan.get(lane, 0.0))
        volume = self._distance_to_volume(distance) * self.sfx_volume
        channel.set_volume(left * volume, right * volume)
        channel.play(sound, loops=-1)
        self.looping_instances[tag] = SoundInstance(name=name, channel=channel, lane=lane, distance=distance)

    def stop_loop(self, tag: str) -> None:
        instance = self.looping_instances.pop(tag, None)
        if instance:
            instance.channel.stop()

    def update_loop(self, tag: str, lane: int, distance: float) -> None:
        instance = self.looping_instances.get(tag)
        if not instance:
            return
        left, right = self._pan_to_stereo(self.config.game.lane_pan.get(lane, 0.0))
        volume = self._distance_to_volume(distance) * self.sfx_volume
        instance.channel.set_volume(left * volume, right * volume)
        instance.lane = lane
        instance.distance = distance
    
    def update_loop_with_pan(self, tag: str, pan: float, distance: float) -> None:
        instance = self.looping_instances.get(tag)
        if not instance:
            return
        left, right = self._pan_to_stereo(pan)
        volume = self._distance_to_volume(distance) * self.sfx_volume
        instance.channel.set_volume(left * volume, right * volume)
        instance.distance = distance

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
