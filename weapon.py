from collections import deque
import math
import pygame as pg
from doomsettings import SOUNDS, H_WIDTH, HEIGHT, PLAYER_STEP_FREQUENCY, WEAPON_BOB_X_AMPLITUDE, WEAPON_BOB_Y_AMPLITUDE
from sounds import SoundEffect

class Weapon:
    def __init__(self, engine):
        self.engine = engine
        self.sprite_bases = {
            "none":     "PUN",
            "chainsaw": "SAW",
            "pistol":   "PIS",
            "shotgun":  "SHT",
            "chaingun": "CHG",
        }
        self.weapon_sprites = {}
        self.muzzle_flash_sprites = {}
        for k, v in self.sprite_bases.items():
            self.weapon_sprites[k] = deque([s for s in self.engine.view_renderer.sprites if s.startswith(f"{v}G")])
            self.muzzle_flash_sprites[k] = deque([s for s in self.engine.view_renderer.sprites if s.startswith(f"{v}F")])
        self.shooting = False
        self.reloading = False
        self.animation_time_prev = pg.time.get_ticks()
        self.animation_trigger = False
        self.animation_time = 30 
        self.frame_counter = 0
        self.sound_effects = {}
        for type in self.sprite_bases:
            if type in SOUNDS:
                self.sound_effects[type] = SoundEffect(SOUNDS[type], self.engine)
        self.current_weapon = "pistol"
        self.x_bob_offset = 0
        self.y_bob_offset = 0
        self.pos = (0,0)
        self.current_sprite_names = ["PISGA0"]
        self.current_sprites = []

    def update(self):
        self.set_current_sprite()
        self.set_weapon_offsets()
        self.set_sprite_position()
        self.check_animation_time()
        self.animate_shot()

    def animate_shot(self):
        if self.reloading or self.shooting:
            if self.animation_trigger:
                self.frame_counter += 1


    def set_sprite_position(self):
        if len(self.current_sprites) == 0:
            return
        x_pos = H_WIDTH - self.current_sprites[0].get_width() //2 + self.x_bob_offset 
        y_pos = HEIGHT - self.current_sprites[0].get_height() - self.engine.view_renderer.status_bar.get_height()+self.y_bob_offset + self.engine.player.weapon_y_offset
        self.pos = (x_pos, y_pos)        

    def set_current_sprite(self):
        if not self.shooting and not self.reloading:
            sprite_name = f"{self.sprite_bases[self.current_weapon]}GA0"
            self.current_sprites = [self.engine.view_renderer.sprites[sprite_name]]
        if self.shooting:
            if self.frame_counter == len(self.muzzle_flash_sprites[self.current_weapon]):
                self.shooting = False
                self.reloading = True
            else:                             
                base_sprite_name = self.weapon_sprites[self.current_weapon][self.frame_counter]
                flash_sprite_name = self.muzzle_flash_sprites[self.current_weapon][self.frame_counter]
                self.current_sprites = [
                    self.engine.view_renderer.sprites[base_sprite_name],
                    self.engine.view_renderer.sprites[flash_sprite_name]
                ]
        if self.reloading:
            if self.frame_counter == len(self.weapon_sprites[self.current_weapon]):
                self.reloading = False
                self.frame_counter = 0
            else:
                base_sprite_name = self.weapon_sprites[self.current_weapon][self.frame_counter]
                self.current_sprites = [
                    self.engine.view_renderer.sprites[base_sprite_name],
                ]

    def play_sound(self):
        current_weapon = self.engine.player.current_weapon
        if current_weapon in self.sound_effects:
            self.sound_effects[current_weapon].play()

    def check_animation_time(self):
        self.animation_trigger = False
        time_now = pg.time.get_ticks()
        if time_now - self.animation_time_prev > self.animation_time:
            self.animation_time_prev = time_now
            self.animation_trigger = True


    def set_weapon_offsets(self):
        """
        Horizontal and vertical 'weapon bob' - sinusoidal oscillation
        """
        self.x_bob_offset = WEAPON_BOB_X_AMPLITUDE * math.sin(self.engine.player.step_phase * PLAYER_STEP_FREQUENCY)
        self.y_bob_offset = WEAPON_BOB_Y_AMPLITUDE * math.cos(self.engine.player.step_phase * PLAYER_STEP_FREQUENCY)
        