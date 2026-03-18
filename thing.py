import math
import pygame as pg

from enum import Enum
from doomsettings import *


class Thing:
    def __init__(self, engine, pos, angle):
        self.engine = engine
        self.pos = pos
        self.angle = angle - 90 # for some reason
        self.sprite_name = ""
        self.scaled_sprite = None
        self.blit_pos = None
        self.sprite_cache = {}
        self.current_frame = "A"
        self.orig_image_size = None
        self.clip_top = [0] * WIDTH
        self.clip_bottom = [HEIGHT -1] * WIDTH
        self.shootable = False
        self.line_of_sight = False
        self.exists = True

    def pre_cache(self, name_base):
        """
        Upon instantiation, calculate and store all sizes
        of all frames/angles of the sprite in the object handler.
        Scale in increments of 8 pixels

        Parameters
        ==========
        name_base: 4-letter sprite name base.
        """
        # if sprites for this monster type already cached, just return.
        if name_base in self.engine.object_handler.sprite_cache:
            return
        # otherwise, find all angles and scales, and store in object handler's sprite cache
        sprite_cache = {}
        sprites = {k: v for k, v in self.engine.view_renderer.asset_data.sprites.items() if k.startswith(name_base)}
        for k, v in sprites.items():
            img_size = v.get_size()
            aspect_ratio = img_size[0]/img_size[1]
            # max height - get nearest multiple of 8
            max_height = img_size[1] * MAX_SPRITE_HEIGHT_RATIO
            max_height = 8 * (max_height//8)
            # decode the naming convention - fifth character
            # is the frame of animation
            frame = k[4]
            if not frame in sprite_cache:
                sprite_cache[frame] = {}
            # remaining characters are angle at which we view the NPC
            view = k[5:]
            if not view in sprite_cache[frame]:
                sprite_cache[frame][view] = {}
            for height in range(8, int(max_height), 8):
                img = pg.transform.scale(v,(height*aspect_ratio, height))
                sprite_cache[frame][view][height] = img
        self.engine.object_handler.sprite_cache[name_base] = sprite_cache

    def calculate_angle(self):
        """
        calculate the angle between the thing's facing
        direction, and the vector from the thing to the player.
        return a number between 0 and 8, indicating which
        sprite (or set of sprites) to use.

        Returns
        =======
            rotation_index: int, between 1 and 8.
        """
        vec_to_player = self.pos - self.engine.player.pos
        angle_to_player = math.atan2(-vec_to_player.y, vec_to_player.x)
        angle_diff = (angle_to_player - math.radians(self.angle-90)) % (2*math.pi)
        # Each rotation sector is 45° (π/4)
        rotation_index = int((angle_diff + math.pi / 8) // (math.pi / 4)) + 1

        if rotation_index > 8:
            rotation_index = 1  # wraparound

        return rotation_index
    
    def update(self):
        if self.exists:
            self.scaled_sprite, self.blit_pos, self.dist = self.scale_and_position()
        else:
            self.scaled_sprite = None

    def get_y_offset(self, proj_plane_dist, view_y):
        """
        y position to be rendered on screen depends on floor height and 
        player's eye height, as well as the sprite size.
        """
        floor_height = self.engine.bsp.get_sub_sector_height(self.pos)
        # player eye height takes into account the head bob animation
        player_eye_height = self.engine.player.get_view_height()
        vertical_offset = floor_height  - player_eye_height + self.world_height - self.extra_y_offset
        screen_vertical_offset = (vertical_offset / view_y) * proj_plane_dist
        return int(screen_vertical_offset) 

    def scale_and_position(self):
        
        dx = self.pos.x - self.engine.player.pos.x
        dy = self.pos.y - self.engine.player.pos.y

        # inverse player rotation
        sin_a = math.sin(-math.radians(self.engine.player.angle-90))
        cos_a = math.cos(-math.radians(self.engine.player.angle-90))

        # rotate into player view space
        view_x = dx * cos_a - dy * sin_a
        view_y = dx * sin_a + dy * cos_a

        # don't render if behind the player
        if view_y <= 0:
            return None, None, None
        
        # distance from player to sprite (for scaling)
        dist = math.hypot(view_x, view_y)
        
        # screen projection
        proj_plane_dist = WIDTH / (2 * math.tan(FOV_RAD /2))
        screen_x = int(H_WIDTH + (view_x/view_y) * proj_plane_dist)
        sprite_scale = SPRITE_PIX_RATIO * proj_plane_dist/dist
        
        angle = self.calculate_angle()
        sprite = self.retrieve_cached_sprite(angle, sprite_scale)
    
        sprite_height, sprite_width = sprite.get_size()

        y_offset = self.get_y_offset(proj_plane_dist, view_y)
  
        blit_x = screen_x - sprite_width // 2
        blit_y = HEIGHT // 2 - sprite_height // 2 - y_offset

        return sprite, (blit_x, blit_y), dist

    def retrieve_cached_sprite(self, angle, scale):
        """ 
        find all the sprites for the current animation frame
        """
        sprite_angle_dict = self.engine.object_handler.sprite_cache[self.sprite_name_base][self.current_frame]
        flip = False
        # find the scaled sprites for the viewing angle
        for k, v in sprite_angle_dict.items():
            if str(angle) in k:
                break

        if len(k) == 3:
            # same image flipped for e.g. angles 2 and 8, or 4 and 6
            if k[0] == str(angle):
                flip = True
        # sprite_size_dict, keyed by sprite height in pixels
        sprite_size_dict = v
        sizes = sorted(list(sprite_size_dict.keys()))
        orig_height = sizes[-1] / MAX_SPRITE_HEIGHT_RATIO
        target_height = orig_height * scale
        if target_height < sizes[0]:
            sprite_height = sizes[0]
        elif target_height > sizes[-1]:
            sprite_height = sizes[-1]
        else:
            sprite_height = 8* (target_height // 8)
        sprite = sprite_size_dict[sprite_height]
        if flip:
            sprite = pg.transform.flip(sprite, True, False)
        return sprite