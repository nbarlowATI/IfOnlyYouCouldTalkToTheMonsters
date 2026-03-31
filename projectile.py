import pygame as pg
from pygame.math import Vector2 as vec2

from thing import Thing
from bsp import circle_segment_collision
from doomsettings import *
from sounds import SoundEffect

FIREBALL_RADIUS = 6  # much smaller than PLAYER_SIZE; only collide with solid walls
ROCKET_RADIUS = 8


class ImpFireball(Thing):
    """
    BAL1 sprite: frames A/B = flight (rotation-independent, view key "0"),
                 frames E/F = explosion.
    """
    FLIGHT_FRAMES = ["A", "B"]
    EXPLODE_FRAMES = ["C", "D"]
    ANIMATION_SPEED_MS = 80   # ms per frame

    def __init__(self, engine, pos, direction, spawn_z, dz_speed):
        # angle unused for rendering (BAL1 is rotation-independent) but
        # Thing.__init__ stores it, so pass 0.
        super().__init__(engine, vec2(pos), 0)
        self.sprite_name_base = "BAL1"
        self.world_height = 56
        self.extra_y_offset = 20
        # Explicit world-Z of the fireball's centre.  We do NOT use
        # get_sub_sector_height() each frame because the fireball travels into
        # 2D map regions belonging to lower sub-sectors, snapping the sprite
        # to the wrong height.  dz_speed advances z each frame so the fireball
        # travels diagonally toward the player's height.
        self.spawn_z = spawn_z
        self.dz_speed = dz_speed  # world-Z change per ms
        self.direction = direction.normalize()
        self.is_exploding = False
        self.frame_index = 0
        self.current_frame = self.FLIGHT_FRAMES[0]
        self.anim_time_prev = pg.time.get_ticks()
        self.pre_cache(self.sprite_name_base)

    # BAL1 uses rotation "0" (not 1-8), so always return 0.
    def calculate_angle(self):
        return 0

    def get_y_offset(self, proj_plane_dist, view_y):
        """
        Use the fixed spawn_z instead of get_sub_sector_height(self.pos).
        The parent implementation samples the floor height at the fireball's
        current 2D position, which jumps to the lower area's floor the moment
        the fireball travels off the platform edge.
        """
        player_eye_height = self.engine.player.get_view_height()
        vertical_offset = self.spawn_z - player_eye_height
        return int((vertical_offset / view_y) * proj_plane_dist)

    def _check_animation_time(self):
        now = pg.time.get_ticks()
        if now - self.anim_time_prev >= self.ANIMATION_SPEED_MS:
            self.anim_time_prev = now
            return True
        return False

    def _advance_frame(self):
        if not self._check_animation_time():
            return
        if self.is_exploding:
            self.frame_index += 1
            if self.frame_index >= len(self.EXPLODE_FRAMES):
                # explosion finished — remove from world
                self.exists = False
                return
            self.current_frame = self.EXPLODE_FRAMES[self.frame_index]
        else:
            self.frame_index = (self.frame_index + 1) % len(self.FLIGHT_FRAMES)
            self.current_frame = self.FLIGHT_FRAMES[self.frame_index]

    def explode(self, deal_damage=False):
        if self.is_exploding:
            return
        self.is_exploding = True
        self.frame_index = 0
        self.current_frame = self.EXPLODE_FRAMES[0]
        if deal_damage:
            self.engine.player.take_damage(IMP_FIREBALL_DAMAGE)

    def _hits_solid_wall(self, pos):
        """
        Check pos against every solid (one-sided) wall segment using a small
        fireball radius.  We skip portal walls (back_sector is not None) so the
        fireball flies through doorways and open space correctly.
        trace_collision() is intentionally NOT used here because it is hardcoded
        to PLAYER_SIZE=16 and traverses all sub-sectors unconditionally, which
        causes fireballs to explode immediately whenever an Imp stands near any wall.
        """
        sub_sectors = self.engine.bsp.sub_sectors
        segments = self.engine.bsp.segments
        for ss in sub_sectors:
            for i in range(ss.seg_count):
                seg = segments[ss.first_seg_id + i]
                if seg.back_sector is not None:
                    continue  # two-sided portal wall — fireball passes through
                if circle_segment_collision(pos, seg.start_vertex, seg.end_vertex, FIREBALL_RADIUS):
                    return True
        return False

    def _move(self):
        if self.is_exploding:
            return
        dt = self.engine.dt
        step = self.direction * IMP_FIREBALL_SPEED * dt
        new_pos = self.pos + step

        if self._hits_solid_wall(new_pos):
            self.explode()
            return

        self.pos = new_pos
        self.spawn_z += self.dz_speed * dt

        # player collision
        if self.pos.distance_to(self.engine.player.pos) < PLAYER_SIZE:
            self.explode(deal_damage=True)

    def update(self):
        if not self.exists:
            return
        self._move()
        self._advance_frame()
        super().update()  # recalculates scaled_sprite / blit_pos / dist


class PlayerRocket(Thing):
    """
    MISL sprite: frame A = flight (rotations 1-8),
                 frames B/C/D = explosion (rotation 0).
    """
    FLIGHT_FRAMES  = ["A"]
    EXPLODE_FRAMES = ["B", "C", "D"]
    ANIMATION_SPEED_MS = 60

    def __init__(self, engine, pos, direction, spawn_z):
        super().__init__(engine, vec2(pos), 0)
        self.sprite_name_base = "MISL"
        self.world_height = 32
        self.extra_y_offset = 20
        self.spawn_z = spawn_z
        self.direction = direction.normalize()
        self.is_exploding = False
        self.frame_index = 0
        self.current_frame = self.FLIGHT_FRAMES[0]
        self.anim_time_prev = pg.time.get_ticks()
        self.explode_sound = SoundEffect(SOUNDS['rocket_explode'], engine)
        self.pre_cache(self.sprite_name_base)

    def calculate_angle(self):
        if self.is_exploding:
            return 0
        # Compute which of the 8 rotation frames the player sees, based on
        # the rocket's actual travel direction rather than self.angle (which is 0).
        to_player = self.engine.player.pos - self.pos
        if to_player.magnitude() == 0:
            return 5
        to_player_n = to_player.normalize()
        # atan2 with negated y to convert Doom (y-down) → standard math (y-up)
        fwd_angle    = math.atan2(-self.direction.y, self.direction.x)
        player_angle = math.atan2(-to_player_n.y,   to_player_n.x)
        angle_diff   = (player_angle - fwd_angle) % (2 * math.pi)
        rotation_index = int((angle_diff + math.pi / 8) // (math.pi / 4)) + 1
        if rotation_index > 8:
            rotation_index = 1
        return rotation_index

    def get_y_offset(self, proj_plane_dist, view_y):
        player_eye_height = self.engine.player.get_view_height()
        vertical_offset = self.spawn_z - player_eye_height
        return int((vertical_offset / view_y) * proj_plane_dist)

    def _check_animation_time(self):
        now = pg.time.get_ticks()
        if now - self.anim_time_prev >= self.ANIMATION_SPEED_MS:
            self.anim_time_prev = now
            return True
        return False

    def _advance_frame(self):
        if not self._check_animation_time():
            return
        if self.is_exploding:
            self.frame_index += 1
            if self.frame_index >= len(self.EXPLODE_FRAMES):
                self.exists = False
                return
            self.current_frame = self.EXPLODE_FRAMES[self.frame_index]
        else:
            self.frame_index = (self.frame_index + 1) % len(self.FLIGHT_FRAMES)
            self.current_frame = self.FLIGHT_FRAMES[self.frame_index]

    def _apply_splash_damage(self):
        targets = list(self.engine.object_handler.npcs) + [self.engine.player]
        for target in targets:
            dist = (target.pos - self.pos).magnitude()
            if dist < ROCKET_EXPLOSION_RADIUS:
                damage = int(ROCKET_EXPLOSION_DAMAGE * (1 - dist / ROCKET_EXPLOSION_RADIUS))
                target.take_damage(damage)

    def explode(self):
        if self.is_exploding:
            return
        self.is_exploding = True
        self.frame_index = 0
        self.current_frame = self.EXPLODE_FRAMES[0]
        self.explode_sound.play()
        self._apply_splash_damage()

    def _hits_solid_wall(self, pos):
        sub_sectors = self.engine.bsp.sub_sectors
        segments = self.engine.bsp.segments
        for ss in sub_sectors:
            for i in range(ss.seg_count):
                seg = segments[ss.first_seg_id + i]
                if seg.back_sector is not None:
                    continue
                if circle_segment_collision(pos, seg.start_vertex, seg.end_vertex, ROCKET_RADIUS):
                    return True
        return False

    def _move(self):
        if self.is_exploding:
            return
        dt = self.engine.dt
        new_pos = self.pos + self.direction * ROCKET_SPEED * dt

        if self._hits_solid_wall(new_pos):
            self.explode()
            return

        self.pos = new_pos

        # Direct NPC hit
        for npc in self.engine.object_handler.npcs:
            if not npc.exists or npc.health <= 0:
                continue
            if self.pos.distance_to(npc.pos) < npc.radius:
                self.explode()
                return

    def update(self):
        if not self.exists:
            return
        self._move()
        self._advance_frame()
        super().update()
