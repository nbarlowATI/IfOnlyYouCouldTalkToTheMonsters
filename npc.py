import math
import random
import pygame as pg

from enum import Enum
from doomsettings import *
from thing import Thing
from projectile import ImpFireball
from sounds import SoundEffect
from character_contexts import npc_types, names as npc_names

class NPCState(Enum):
    standing = 0
    walking = 1
    chasing = 2
    shooting = 3
    getting_hit = 4
    dying = 5
    dead = 6


class NPC(Thing):
    PAIN_DURATION = 400       # ms the pain frame is shown
    DEATH_FRAME_DURATION = 150  # ms per death animation frame
    WALK_FRAME_DURATION = 150   # ms per walk animation frame
    SHOOT_FRAME_DURATION = 120  # ms per shoot animation frame

    def __init__(self, engine, pos, angle):
        super().__init__(engine, pos, angle)
        self.engine = engine
        self.state = NPCState.standing
        self.shootable = False
        self.line_of_sight = False
        self.health = 100
        self.is_in_pain = False
        self.pain_start_time = 0
        self.pain_frame = None    # set by subclasses
        self.pain_sound = None    # set by subclasses
        self.death_frames = []    # set by subclasses
        self.death_sounds = []    # set by subclasses (list so we can pick randomly)
        self.death_frame_index = 0
        self.death_frame_time = 0
        self.walk_frame_index = 0
        self.walk_frame_time = 0
        self.walking_frame_suffixes = []  # set by subclasses
        self.patrol_angle = angle        # direction of movement in degrees
        self.patrol_turn_time = 0        # timestamp of last random turn
        self.radius = 20                 # collision radius (subclasses may override)
        # Hitscan shooting — set by subclasses that can shoot
        self.shoot_damage = 0
        self.shoot_cooldown = 0
        self.shoot_range = 0
        self.shoot_prob = 0.0
        self.shoot_sound = None
        self.last_shoot_time = 0
        self.shooting_frames = []    # set by subclasses
        self.is_shooting_anim = False
        self.shoot_anim_index = 0
        self.shoot_anim_time = 0
        # Character identity — subclasses set TYPE_ID, then call _init_character_context()
        self.npc_name = "Unknown"
        self.friendliness = 50
        self.conversation_history = []   # list of {"player": str, "npc": str}
        self.waiting_for_llm = False

    def _init_character_context(self):
        ctx = next((t for t in npc_types if t['type_id'] == self.TYPE_ID), None)
        if ctx:
            self.friendliness = ctx['friendliness']
        self.npc_name = random.choice(npc_names.get(self.TYPE_ID, ["Unknown"]))

    def get_character_context(self):
        ctx = next((t for t in npc_types if t['type_id'] == self.TYPE_ID), None)
        if not ctx:
            return f"Your name is {self.npc_name}. You are a creature in DOOM."
        return (
            f"Your name is {self.npc_name}. "
            f"You are a {ctx['species']}. "
            f"Your current friendliness toward the player is {self.friendliness} out of 100. "
            f"Your original home was {ctx['original_home']}. "
            f"Your goal is: {ctx['goal']}. "
            f"You feel solidarity with: {', '.join(ctx['friends'])}. "
            f"You distrust: {', '.join(ctx['enemies'])}."
        )

    def _load_sound(self, lump_name):
        """Load a sound effect, returning None if the lump isn't in the WAD."""
        if lump_name in self.engine.wad_data.sound_effects:
            return SoundEffect(lump_name, self.engine)
        return None

    def calculate_angle(self):
        """Return 0 (rotation-independent) when dying or dead; otherwise normal."""
        if self.state in (NPCState.dying, NPCState.dead):
            return 0
        return super().calculate_angle()

    def get_y_offset(self, proj_plane_dist, view_y):
        """
        Death sprites are flat on the floor; their visual centre is at floor
        level, so omit the world_height / extra_y_offset correction that
        positions standing sprites at mid-torso height.
        """
        if self.state in (NPCState.dying, NPCState.dead):
            floor_height = self.engine.bsp.get_sub_sector_height(self.pos)
            player_eye_height = self.engine.player.get_view_height()
            vertical_offset = floor_height - player_eye_height
            return int((vertical_offset / view_y) * proj_plane_dist)
        return super().get_y_offset(proj_plane_dist, view_y)

    def _move(self, dt):
        step = pg.Vector2(NPC_WALK_SPEED * dt, 0)
        step.rotate_ip(-self.patrol_angle)
        new_pos = self.pos + step
        collision_segs = self.engine.bsp.trace_collision(self.pos, new_pos, self.radius)
        if not collision_segs:
            self.pos = new_pos
            # Face the direction of travel
            self.angle = 270 - math.degrees(math.atan2(step.y, step.x))
        else:
            # Hit a wall — pick a new random patrol direction
            self.patrol_angle = random.uniform(0, 360)
            self.patrol_turn_time = pg.time.get_ticks()

    def _try_shoot_hitscan(self, now):
        if not self.shoot_damage:
            return
        if not self.line_of_sight:
            return
        dp = self.engine.player.pos - self.pos
        if dp.magnitude() > self.shoot_range:
            return
        if now - self.last_shoot_time < self.shoot_cooldown:
            return
        self.last_shoot_time = now
        if self.shooting_frames:
            self.is_shooting_anim = True
            self.shoot_anim_index = 0
            self.shoot_anim_time = now
            self.current_frame = self.shooting_frames[0]
        if random.random() < self.shoot_prob:
            self.engine.player.take_damage(self.shoot_damage)
            if self.shoot_sound:
                self.shoot_sound.play()

    def _trigger_pain(self):
        if self.pain_frame:
            frame_cache = self.engine.object_handler.sprite_cache.get(self.sprite_name_base, {})
            if self.pain_frame in frame_cache:
                self.current_frame = self.pain_frame
        if self.pain_sound:
            self.pain_sound.play()
        self.is_in_pain = True
        self.pain_start_time = pg.time.get_ticks()

    def _trigger_death(self):
        self.state = NPCState.dying
        self.is_in_pain = False
        self.death_frame_index = 0
        self.death_frame_time = pg.time.get_ticks()
        if self.death_frames:
            self.current_frame = self.death_frames[0]
        if self.death_sounds:
            random.choice(self.death_sounds).play()

    def _advance_death(self):
        now = pg.time.get_ticks()
        if now - self.death_frame_time < self.DEATH_FRAME_DURATION:
            return
        self.death_frame_time = now
        self.death_frame_index += 1
        if self.death_frame_index >= len(self.death_frames):
            # Clamp to last frame and mark as fully dead
            self.death_frame_index = len(self.death_frames) - 1
            self.state = NPCState.dead
            return
        self.current_frame = self.death_frames[self.death_frame_index]

    def update(self):
        super().update()

        # Fully dead: just lie on the floor, no further logic
        if self.state == NPCState.dead:
            self.shootable = False
            return

        # Dying: advance the animation and nothing else
        if self.state == NPCState.dying:
            self._advance_death()
            return

        # Talk mode: freeze all alive NPCs (no movement, animation, or attacks)
        if self.engine.talk_mode:
            return

        now = pg.time.get_ticks()

        # Recover from pain after duration elapses
        if self.is_in_pain and now - self.pain_start_time > self.PAIN_DURATION:
            self.is_in_pain = False
            self.walk_frame_index = 0
            self.walk_frame_time = now
            self.state = NPCState.walking

        # Advance shoot animation
        if self.is_shooting_anim:
            if now - self.shoot_anim_time > self.SHOOT_FRAME_DURATION:
                self.shoot_anim_time = now
                self.shoot_anim_index += 1
                if self.shoot_anim_index >= len(self.shooting_frames):
                    self.is_shooting_anim = False
                    self.walk_frame_index = 0
                else:
                    self.current_frame = self.shooting_frames[self.shoot_anim_index]

        # Advance walk animation when not in pain/shooting/dying/dead
        if not self.is_in_pain and not self.is_shooting_anim and self.walking_frame_suffixes:
            if now - self.walk_frame_time > self.WALK_FRAME_DURATION:
                self.walk_frame_time = now
                self.walk_frame_index = (self.walk_frame_index + 1) % len(self.walking_frame_suffixes)
                self.current_frame = self.walking_frame_suffixes[self.walk_frame_index]

        # Patrol movement
        if not self.is_in_pain:
            dp = self.engine.player.pos - self.pos
            if dp.magnitude() < NPC_CHASE_RADIUS:
                # Steer toward player
                self.patrol_angle = -math.degrees(math.atan2(dp.y, dp.x))
            elif now - self.patrol_turn_time > NPC_PATROL_TURN_INTERVAL:
                # Periodic random wander turn
                self.patrol_angle = random.uniform(0, 360)
                self.patrol_turn_time = now
            self._move(self.engine.dt)

        # Hitscan shooting at player
        self._try_shoot_hitscan(now)

        # Take damage when in crosshair and player fires
        if self.shootable and self.engine.weapon.shooting:
            self.health -= WEAPON_DAMAGE[self.engine.player.current_weapon]
            if self.health <= 0:
                self._trigger_death()
            elif not self.is_in_pain:
                self.state = NPCState.getting_hit
                self._trigger_pain()


class ZombieMan(NPC):
    TYPE_ID = 3004

    def __init__(self, engine, pos, angle):
        super().__init__(engine, pos, angle)
        self._init_character_context()
        self.sprite_name_base = "POSS"
        self.standing_frame_suffixes = ["A"]
        self.walking_frame_suffixes = ["B","C","D"]
        self.world_height = 56
        self.extra_y_offset = 20
        self.pain_frame = "G"
        self.pain_sound = self._load_sound("DSPOPAIN")
        self.death_frames = ["H", "I", "J", "K", "L"]
        self.death_sounds = [s for s in [
            self._load_sound("DSPODTH1"),
            self._load_sound("DSPODTH2"),
            self._load_sound("DSPODTH3"),
        ] if s is not None]
        self.shooting_frames = ["E", "F"]
        self.shoot_damage = ZOMBIE_SHOOT_DAMAGE
        self.shoot_cooldown = ZOMBIE_SHOOT_COOLDOWN
        self.shoot_range = ZOMBIE_SHOOT_RANGE
        self.shoot_prob = ZOMBIE_SHOOT_PROB
        self.shoot_sound = self._load_sound("DSPISTOL")
        self.pre_cache(self.sprite_name_base)


class ShotgunGuy(NPC):
    TYPE_ID = 9

    def __init__(self, engine, pos, angle):
        super().__init__(engine, pos, angle)
        self._init_character_context()
        self.sprite_name_base = "SPOS"
        self.standing_frame_suffixes = ["A"]
        self.walking_frame_suffixes = ["B","C","D","E"]
        self.world_height = 56
        self.radius = 20
        self.extra_y_offset = 20
        self.pain_frame = "G"
        self.pain_sound = self._load_sound("DSPOPAIN")
        self.death_frames = ["H", "I", "J", "K", "L"]
        self.death_sounds = [s for s in [
            self._load_sound("DSSGTDTH"),
        ] if s is not None]
        self.shooting_frames = ["F"]
        self.shoot_damage = SHOTGUN_SHOOT_DAMAGE
        self.shoot_cooldown = SHOTGUN_SHOOT_COOLDOWN
        self.shoot_range = SHOTGUN_SHOOT_RANGE
        self.shoot_prob = SHOTGUN_SHOOT_PROB
        self.shoot_sound = self._load_sound("DSSHOTGN")
        self.pre_cache(self.sprite_name_base)


class Imp(NPC):
    TYPE_ID = 3001
    TURN_RANGE = 700  # world units; Imp starts tracking the player within this distance

    def __init__(self, engine, pos, angle):
        super().__init__(engine, pos, angle)
        self._init_character_context()
        self.sprite_name_base = "TROO"
        self.standing_frame_suffixes = ["A"]
        self.walking_frame_suffixes = ["B","C","D","E"]
        self.world_height = 56
        self.radius = 20
        self.extra_y_offset = 20
        self.pain_frame = "H"
        self.pain_sound = self._load_sound("DSIMPPAIN")
        self.death_frames = ["I", "J", "K", "L", "M"]
        self.death_sounds = []  # DSIMPDTH not in DOOM1.WAD shareware
        self.pre_cache(self.sprite_name_base)
        self.last_fire_time = -IMP_FIRE_COOLDOWN

    def _face_player(self):
        """
        Rotate to face the player.  Derived from calculate_angle():
        rotation_index=1 (front-facing sprite toward viewer) when
            angle_diff = (angle_to_player - radians(self.angle-90)) % 2π  ≈  0
        Solving for self.angle gives:
            self.angle = 270 - degrees(atan2(dp.y, dp.x))
        where dp = player.pos - self.pos.
        """
        dp = self.engine.player.pos - self.pos
        self.angle = 270 - math.degrees(math.atan2(dp.y, dp.x))

    def _try_fire(self):
        now = pg.time.get_ticks()
        if now - self.last_fire_time < IMP_FIRE_COOLDOWN:
            return
        dp = self.engine.player.pos - self.pos
        if dp.magnitude() == 0:
            return
        direction = dp.normalize()
        # Offset spawn past the Imp's own radius so the fireball doesn't
        # immediately collide with the wall the Imp is standing against.
        spawn_pos = self.pos + direction * (self.radius + PLAYER_SIZE + 4)
        # Sample floor height at the IMP's position (not spawn_pos) so we get
        # the platform height even if the spawn offset crosses into a lower sector.
        imp_floor = self.engine.bsp.get_sub_sector_height(self.pos)
        # Place the fireball at mid-torso height (matches the Imp's visual centre).
        spawn_z = imp_floor + self.world_height - self.extra_y_offset
        # Vertical speed: glide from spawn_z to player eye height over the
        # horizontal travel distance, so the fireball arrives at the right level.
        horiz_dist = dp.magnitude()
        dz_speed = (self.engine.player.height - spawn_z) / horiz_dist * IMP_FIREBALL_SPEED
        fireball = ImpFireball(self.engine, spawn_pos, direction, spawn_z, dz_speed)
        self.engine.object_handler.projectiles.append(fireball)
        self.last_fire_time = now

    def update(self):
        super().update()
        # Don't move or fire if dying/dead
        if self.state in (NPCState.dying, NPCState.dead):
            return
        dp = self.engine.player.pos - self.pos
        if dp.magnitude() < self.TURN_RANGE:
            self._face_player()
        if self.line_of_sight:
            self._try_fire()
