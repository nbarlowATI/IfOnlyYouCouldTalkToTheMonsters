import math
import random

from pygame.math import Vector2 as vec2
import pygame as pg

from doomsettings import *
from data_types import Seg
from sounds import SoundEffect

class Player:
    def __init__(self, engine):
        self.engine = engine
        self.thing = self.engine.wad_data.things[0]
        self.pos = self.thing.pos
        self.angle = self.thing.angle
        self.DIAG_MOVE_CORR = 1/math.sqrt(2)
        self.height = PLAYER_HEIGHT
        self.view_height = self.height
        self.size = PLAYER_SIZE
        self.step_phase = 0
        self.climbing_or_falling = False
        self.active_door = None
        self.current_weapon = 'pistol'
        self.selected_weapon = 'pistol'
        self.lowering_weapon = False
        self.raising_weapon = False
        self.weapon_y_offset = 0
        self.health = 100
        self.face_img = 'STFST00'
        self.is_in_pain = False
        self.pain_start_time = 0
        self.PAIN_DURATION = 500  # ms the red tint lasts
        self.HEALTH_TINT_DURATION = 300  # ms the blue tint lasts
        self.health_pickup_time = 0
        self.armor = 0
        self.ARMOR_TINT_DURATION = 300
        self.armor_pickup_time = 0
        self.ammo = dict(AMMO_START)
        self.max_ammo = dict(AMMO_MAX)
        pain_lump = "DSPLPAIN" if "DSPLPAIN" in self.engine.wad_data.sound_effects else "DSPOPAIN"
        self.pain_sound = SoundEffect(pain_lump, self.engine)
        item_lump = "DSITEMUP" if "DSITEMUP" in self.engine.wad_data.sound_effects else "DSWPNUP"
        self.item_sound = SoundEffect(item_lump, self.engine)
        self.inventory = {'none', 'pistol'}
        self.friends = {}   # {"E1M1": [{"name": "Magnus", "species": "ZombieMan"}, ...]}
        pickup_lump = "DSWPNUP" if "DSWPNUP" in self.engine.wad_data.sound_effects else "DSPISTOL"
        self.pickup_sound = SoundEffect(pickup_lump, self.engine)
        self.shooting = False
        self.reloading = False
        

    def get_view_height(self):
        # sinusoid with time as we step
        oscillation = PLAYER_STEP_AMPLITUDE * math.sin(self.step_phase * PLAYER_STEP_FREQUENCY)
        self.view_height = self.height + oscillation
        return self.view_height

    def get_height(self):
        target_height = PLAYER_HEIGHT + self.engine.bsp.get_sub_sector_height()
        if self.height > target_height:
            # falling
            self.climbing_or_falling = True
            fall_dist = PLAYER_FALL_SPEED * self.engine.dt
            self.height = max(self.height - fall_dist, target_height)
        elif self.height < target_height:
            # climbing
            self.climbing_or_falling = True
            climb_dist = PLAYER_CLIMB_SPEED * self.engine.dt
            self.height = min(self.height + climb_dist, target_height)
        else:
            self.height = target_height
            self.climbing_or_falling = False

    def set_face_image(self):
        if self.health > 80:
            # select randomly
            self.face_img = random.choice(
                [
                'STFST00', 'STFST01', 'STFTL10',
                'STFTR10', 'STFOUCH0', 'STFKILL0',
                'STFEVL0',
                ]
            )

    def take_damage(self, amount):
        self.health = max(0, self.health - amount)
        self.is_in_pain = True
        self.pain_start_time = pg.time.get_ticks()
        self.pain_sound.play()

    def handle_fire_event(self, event):
        if event.button == 1 and not self.engine.weapon.shooting and not self.engine.weapon.reloading:
            ammo_type = WEAPON_AMMO_TYPE.get(self.current_weapon)
            if ammo_type and self.ammo[ammo_type] <= 0:
                return
            self.engine.weapon.play_sound()
            self.engine.weapon.shooting = True
            if ammo_type:
                self.ammo[ammo_type] -= 1


    def update(self):
        if self.is_in_pain and pg.time.get_ticks() - self.pain_start_time > self.PAIN_DURATION:
            self.is_in_pain = False
        self.get_height()
        self.get_view_height()
        self.control()
        self.mouse_control()
        if self.active_door:
            self.active_door.update()
        if self.selected_weapon != self.engine.weapon.current_weapon \
            and not self.lowering_weapon:
            self.lowering_weapon = True
        if self.raising_weapon:
            if self.weapon_y_offset <= 0:
                self.raising_weapon = False
            else:
                self.weapon_y_offset -= WEAPON_CHANGE_SPEED
        if self.lowering_weapon:
            if self.weapon_y_offset >= MAX_WEAPON_OFFSET:
                self.lowering_weapon = False
                self.raising_weapon = True
                self.engine.weapon.current_weapon = self.selected_weapon
                self.current_weapon = self.selected_weapon
            else:
                self.weapon_y_offset += WEAPON_CHANGE_SPEED
    


    def control(self):
        # if in debug mode or talk mode, disable all movement
        if self.engine.debug_mode or self.engine.talk_mode:
            return
        speed = PLAYER_SPEED * self.engine.dt
        rot_speed = PLAYER_ROT_SPEED * self.engine.dt

        key_state = pg.key.get_pressed()
        if key_state[pg.K_LEFT]:
            self.angle += rot_speed
        if key_state[pg.K_RIGHT]:
            self.angle -= rot_speed
       
        inc = vec2(0)
        if key_state[pg.K_a]:
            inc += vec2(0, speed)
        if key_state[pg.K_d]:
            inc += vec2(0, -speed)
        if key_state[pg.K_w]:
            inc += vec2(speed, 0)
        if key_state[pg.K_s]:
            inc += vec2(-speed,0)

        if inc.x and inc.y:
            inc *= self.DIAG_MOVE_CORR
        if inc.magnitude() > 0 and not self.climbing_or_falling:
            self.step_phase += self.engine.dt

        inc.rotate_ip(self.angle)
        new_pos = self.pos + inc
        collision_segs = self.engine.bsp.trace_collision(self.pos, new_pos)
        if len(collision_segs) == 0:
            self.pos = new_pos
        else:
             self.pos = self.handle_collision(inc, collision_segs)

    # This function is called any time the player's movement
    # would come within some radius of a segment.  Possible outcomes are:
    # * move as normal, if segment is traversible (e.g. step, or open door)
    # * no movement, if movement is directly into non-traversible segment
    # * slide along wall, if movement is at an angle to non-traversible segment.
    def handle_collision(self, movement, collision_segs):
        pos = self.pos
        # First pass: if any door seg is open, movement goes through immediately.
        for collision_seg in collision_segs:
            if check_segment(collision_seg) != WALL_TYPE.DOOR:
                continue
            if collision_seg.linedef_id in self.engine.doors:
                door = self.engine.doors[collision_seg.linedef_id]
                if door.is_open or door.is_opening:
                    return pos + movement
            else:
                # Door not yet registered — allow passage if ceiling clearance is enough.
                back = collision_seg.back_sector
                if back and (back.ceil_height - back.floor_height) > MIN_ROOM_HEIGHT:
                    return pos + movement
        # Second pass: apply wall physics for everything else.
        for collision_seg in collision_segs:
            wall_type = check_segment(collision_seg)
            if wall_type == WALL_TYPE.PASSABLE:
                pos += movement
            elif wall_type == WALL_TYPE.DOOR:
                pass  # Closed door — treat as solid
            elif wall_type == WALL_TYPE.SOLID_WALL:
                wall_vec = collision_seg.start_vertex - collision_seg.end_vertex
                wall_vec_norm = wall_vec / wall_vec.magnitude()
                dot_product = movement.dot(wall_vec_norm)
                pos += dot_product * wall_vec_norm
            elif wall_type == WALL_TYPE.IMPASSABLE:
                return pos
        return pos

    def mouse_control(self):
        # if in debug mode or talk mode, disable all movement
        if self.engine.debug_mode or self.engine.talk_mode:
            return
        mx, my = pg.mouse.get_pos()
        if mx < MOUSE_BORDER_LEFT or mx > MOUSE_BORDER_RIGHT:
            pg.mouse.set_pos([H_WIDTH, H_HEIGHT])
        self.rel = pg.mouse.get_rel()[0]
        self.rel = max(-MOUSE_MAX_REL, min(MOUSE_MAX_REL, self.rel))
        self.angle -= self.rel * MOUSE_SENSITIVITY * self.engine.dt


    def handle_action(self):
        """
        Called when the action button (space bar) is pressed.
        Send a raycast to see if there are any doors or similar ahead.
        """
        seg = self.engine.raycaster.find_activatable_surface()
        if seg is None or not(isinstance(seg, Seg)):
            return
        if check_segment(seg) == WALL_TYPE.DOOR and seg.linedef_id in self.engine.doors:
            self.engine.doors[seg.linedef_id].toggle_open()

    def pick_up_health(self, amount):
        self.health = min(100, self.health + amount)
        self.item_sound.play()
        self.health_pickup_time = pg.time.get_ticks()

    def pick_up_ammo(self, ammo_type, amount):
        self.ammo[ammo_type] = min(self.max_ammo[ammo_type], self.ammo[ammo_type] + amount)
        self.item_sound.play()

    def pick_up_armor(self, amount):
        self.armor = min(200, self.armor + amount)
        self.item_sound.play()
        self.armor_pickup_time = pg.time.get_ticks()

    def pick_up_weapon(self, weapon_name):
        if weapon_name in self.inventory:
            return
        self.inventory.add(weapon_name)
        self.pickup_sound.play()

    def change_weapon(self, weapon_id):
        """
        Called when number key is pressed
        """
        if weapon_id not in WEAPON_BUTTONS:
            return
        weapon = WEAPON_BUTTONS[weapon_id]
        if weapon not in self.inventory:
            return
        if weapon == self.current_weapon:
            return
        self.selected_weapon = weapon

def check_segment(segment):
    if segment.back_sector is None:
        return WALL_TYPE.SOLID_WALL
    if segment.linedef.line_type == 1:
        return WALL_TYPE.DOOR
    if segment.linedef.flags > 0:
        pass
    floor_diff = segment.back_sector.floor_height - segment.front_sector.floor_height
    ceiling_clearance = segment.back_sector.ceil_height - segment.back_sector.floor_height
 #   print(f"step {floor_diff} clearance {ceiling_clearance}")
    if floor_diff < MAX_STEP_HEIGHT and ceiling_clearance > MIN_ROOM_HEIGHT:

  #      print(f"middle texture {segment.linedef.back_sidedef.middle_texture}")
        return WALL_TYPE.PASSABLE
    return WALL_TYPE.IMPASSABLE
