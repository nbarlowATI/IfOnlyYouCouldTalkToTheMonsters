import pygame as pg
from thing import Thing
from doomsettings import SOUNDS, WEAPON_DAMAGE
from sounds import SoundEffect


class Ornament(Thing):
    def __init__(self, engine, pos, angle, thing_info):
        super().__init__(engine, pos, angle)
        self.sprite_name_base = thing_info["sprite_base"]
        self.world_height = float(thing_info["height"])
        self.radius = float(thing_info["radius"])
        self.pre_cache(self.sprite_name_base)
        self.extra_y_offset = 20

    def update(self):
        super().update()


class ExplodingBarrel(Ornament):
    def __init__(self, engine, pos, angle, thing_info):
        super().__init__(engine, pos, angle, thing_info)
        self.shootable = False
        self.line_of_sight = False
        self.health = 50
        self.extra_y_offset = 30
        self.is_exploding = False
        self.sound_effect = SoundEffect(SOUNDS["barrel_explode"], self.engine)
        # also pre-cache the explosion sprites
        self.pre_cache("BEXP")
        self.explosion_frames=["A","B","C","D","E"]
        self.frame_counter = 0
        self.animation_trigger = False
        self.animation_time = 60 
        self.animation_time_prev = pg.time.get_ticks()

    def explode(self):
        self.is_exploding = True
        self.sound_effect.play()
        self.sprite_name_base = "BEXP"

    def animate_explosion(self):
        if self.animation_trigger:
            self.frame_counter += 1
        if self.frame_counter == len(self.explosion_frames):
            self.frame_counter = 0
            self.is_exploding = False
            self.exists = False
            self.current_frame = None
            self.engine.object_handler.objects.remove(self)
        else:
            self.current_frame = self.explosion_frames[self.frame_counter]

    def check_animation_time(self):
        self.animation_trigger = False
        time_now = pg.time.get_ticks()
        if time_now - self.animation_time_prev > self.animation_time:
            self.animation_time_prev = time_now
            self.animation_trigger = True

    def update(self):
        if not self.exists:
            return
        super().update()
        if self.shootable and self.engine.weapon.shooting:
            self.health -= WEAPON_DAMAGE[self.engine.player.current_weapon]
        if self.health < 0 and not self.is_exploding:
            self.explode()
        if self.is_exploding:
            self.check_animation_time()
            self.animate_explosion()
        
