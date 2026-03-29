from numba import njit
import numpy as np
from doomsettings import *
import math
import random
from random import randrange as rnd
import pygame as pg
import pygame.gfxdraw as gfx
from pygame.math import Vector2 as vec2

class ViewRenderer:
    def __init__(self,engine):
        self.engine = engine
        self.player = engine.player
        self.screen = engine.screen
        self.framebuffer = engine.framebuffer
        self.colours = {}
        self.asset_data = engine.wad_data.asset_data
        self.palette = self.asset_data.palette
        self.sprites = self.asset_data.sprites
        self.doomguy = self.asset_data.doomguy_faces
        self.status_bar = self.asset_data.status_bar
        self.hud_numbers = self.asset_data.hud_numbers
        self.ammo_glyphs = self.asset_data.ammo_glyphs
        self.textures = self.asset_data.textures
        self.sky_id = self.asset_data.sky_id
        self.sky_tex = self.asset_data.sky_tex
        self.sky_inv_scale = 160 / HEIGHT
        self.sky_tex_alt = 100
        # z-distance clipping buffer:
        # - a 2D array WIDTHxHEIGHT with each entry being the 
        # distance from the player to the nearest drawn wall at that
        # screen position.
        self.z_buffer = np.full((WIDTH, HEIGHT), np.inf)
        # debug cursor - position of a cursor that can be moved around
        # the screen, and, on demand, give e.g. z-buffer information for
        # that screen location.
        self.debug_cursor = (WIDTH//2, HEIGHT //2)
        pg.font.init()
        self.bubble_font = pg.font.SysFont('arial,helvetica,sans-serif', 28)

    # reset clip buffers every frame
    def reset_clip_buffers(self):
        self.z_buffer.fill(np.inf)

    def update(self):
        if self.engine.debug_mode:
            self.debug_cursor_control()

    def get_colour(self, tex, light_level):
        str_light = str(light_level)
        if tex + str_light not in self.colours:
            tex_id = hash(tex)
            random.seed(tex_id)
            colour = self.palette[rnd(0, 256)]
            colour = colour[0] * light_level, colour[1] * light_level, colour[2] * light_level
            self.colours[tex + str_light] = colour
        return self.colours[tex + str_light] 

    def draw_vline(self, x, y1, y2, tex, light):
        if y1 < y2:
            colour = self.get_colour(tex, light)
            self.draw_column(self.framebuffer, x, y1, y2, colour)

    def draw_sprite(self, sprite):
        if not sprite.scaled_sprite:
            return

        sprite_width = sprite.scaled_sprite.get_width()
        sprite_height = sprite.scaled_sprite.get_height()
        blit_x, blit_y = sprite.blit_pos

        # Flag will be set to true if sprite is drawn in central column of screen
        shootable = False
        # Flag will be set to true if sprite is drawn at all.
        line_of_sight = False

        for i in range(sprite_width):
            screen_column = blit_x + i
            if not (0 <= screen_column < WIDTH):
                continue

            sprite_col_y1 = blit_y
            sprite_col_y2 = blit_y + sprite_height

            for j in range(sprite_height):
                screen_row = blit_y + j
                if not (0 <= screen_row < HEIGHT):
                    continue

                # Check if sprite is closer than geometry at this pixel
                if sprite.dist < self.z_buffer[screen_column, screen_row]:

                    # set flags to say whether npc is in our sights and vice/versa
                    line_of_sight = True
                    if abs(screen_column - H_WIDTH) < 10:
                        shootable = True
                    # Get the pixel colour from the sprite column
                    pixel_colour = sprite.scaled_sprite.get_at((i, j))

                    # Skip fully transparent pixels (alpha == 0)
                    if pixel_colour[:3] == COLOUR_KEY:
                        continue

                    # Draw the pixel
                    self.screen.set_at((screen_column, screen_row), pixel_colour)
  
        sprite.shootable = shootable
        sprite.line_of_sight = line_of_sight
        

    def draw_flat(self, tex_id, light_level, x, y1, y2, world_z):
        if y1 < y2:
            if tex_id == self.sky_id:
                tex_column = 2.2 * (self.player.angle + self.engine.seg_handler.x_to_angle[x])

                self.draw_wall_col(
                    self.framebuffer, self.sky_tex, tex_column, x, y1, y2,
                    self.sky_tex_alt, self.sky_inv_scale, light_level=1.0,
                )
            else:
                flat_tex = self.textures[tex_id]
                # Pass a *view* of the z-buffer column for this x
                z_col = self.z_buffer[x, y1:y2+1]
                self.draw_flat_col(self.framebuffer, flat_tex,
                                   x, y1, y2, light_level, world_z,
                                   self.player.angle, self.player.pos.x, self.player.pos.y,
                                   z_col)
                
    # draw currently selected weapon at the bottom of the screen, but above status bar.
    def draw_weapon(self, sprite_name=None):
        if sprite_name:
            imgs = [self.sprites[sprite_name]]
        else:
            # might be more than one sprite, e.g. muzzle flash overlaid on weapon.
            imgs = self.engine.weapon.current_sprites
        # x_pos = H_WIDTH - img.get_width() //2
        # y_pos = HEIGHT - img.get_height() - self.status_bar.get_height()+self.player.weapon_y_offset
        # pos = (x_pos, y_pos)
        pos = self.engine.weapon.pos
        for img in imgs:
            self.screen.blit(img, pos)

    # draw the status bar at the bottom of the screen
    def draw_status_bar(self):
        img = self.status_bar
        pos = (H_WIDTH - img.get_width() //2, HEIGHT - img.get_height())
        self.screen.blit(img, pos)

    def draw_health(self):
        bar_h = self.status_bar.get_height()
        bar_x = H_WIDTH - self.status_bar.get_width() // 2
        x = bar_x + int(self.status_bar.get_width() * 0.09) + 100
        for ch in f'{max(0, self.player.health)}%':
            glyph = self.hud_numbers.get(ch)
            if glyph:
                y = HEIGHT - bar_h + (bar_h - glyph.get_height()) // 2
                self.screen.blit(glyph, (x, y))
                x += glyph.get_width()

    def draw_talk_bubble(self, text):
        PADDING = 20
        TAIL_H = 24
        TAIL_W = 16
        MIN_W = 320
        MAX_W = WIDTH * 2 // 3
        BG = (255, 255, 220)
        BORDER = (30, 30, 30)
        TEXT_COLOR = (20, 20, 20)
        CURSOR = "|"

        font = self.bubble_font
        display_text = text + CURSOR

        # Word-wrap into lines
        words = display_text.split(' ')
        lines = []
        current = ''
        for word in words:
            test = (current + ' ' + word).strip()
            if font.size(test)[0] > MAX_W - 2 * PADDING:
                if current:
                    lines.append(current)
                current = word
            else:
                current = test
        lines.append(current)

        line_h = font.get_height() + 4
        text_w = max((font.size(l)[0] for l in lines), default=0)
        bubble_w = max(MIN_W, text_w + 2 * PADDING)
        bubble_h = line_h * len(lines) + 2 * PADDING

        bar_h = self.status_bar.get_height()
        # Centre horizontally; sit just above the status bar + tail gap
        bubble_x = H_WIDTH - bubble_w // 2
        bubble_y = HEIGHT - bar_h - TAIL_H - bubble_h

        # Background and border
        bubble_rect = pg.Rect(bubble_x, bubble_y, bubble_w, bubble_h)
        pg.draw.rect(self.screen, BG, bubble_rect, border_radius=12)
        pg.draw.rect(self.screen, BORDER, bubble_rect, 2, border_radius=12)

        # Tail triangle pointing down toward doomguy mouth (centred at H_WIDTH)
        tail_cx = H_WIDTH
        tail_top_y = bubble_y + bubble_h
        tail_bot_y = tail_top_y + TAIL_H
        tail_pts = [
            (tail_cx - TAIL_W, tail_top_y),
            (tail_cx + TAIL_W, tail_top_y),
            (tail_cx, tail_bot_y),
        ]
        pg.draw.polygon(self.screen, BG, tail_pts)
        # Draw the two outer edges of the tail (skip the top edge so it blends with bubble)
        pg.draw.line(self.screen, BORDER,
                     (tail_cx - TAIL_W, tail_top_y), (tail_cx, tail_bot_y), 2)
        pg.draw.line(self.screen, BORDER,
                     (tail_cx + TAIL_W, tail_top_y), (tail_cx, tail_bot_y), 2)

        # Text lines
        for i, line in enumerate(lines):
            surf = font.render(line, True, TEXT_COLOR)
            self.screen.blit(surf, (bubble_x + PADDING, bubble_y + PADDING + i * line_h))

    def draw_npc_bubble(self, npc, text):
        if not npc.scaled_sprite or not text:
            return

        PADDING = 16
        TAIL_H = 22
        TAIL_W = 14
        MIN_W = 200
        MAX_W = WIDTH // 2
        BG = (210, 235, 255)    # light blue — distinct from player's cream bubble
        BORDER = (30, 30, 30)
        TEXT_COLOR = (20, 20, 20)

        font = self.bubble_font

        # Word-wrap text
        words = text.split(' ')
        lines = []
        current = ''
        for word in words:
            test = (current + ' ' + word).strip()
            if font.size(test)[0] > MAX_W - 2 * PADDING:
                if current:
                    lines.append(current)
                current = word
            else:
                current = test
        if current:
            lines.append(current)
        if not lines:
            return

        line_h = font.get_height() + 4
        text_w = max(font.size(l)[0] for l in lines)
        bubble_w = max(MIN_W, text_w + 2 * PADDING)
        bubble_h = line_h * len(lines) + 2 * PADDING

        # NPC head: top-centre of the sprite on screen
        head_x = npc.blit_pos[0] + npc.scaled_sprite.get_width() // 2
        head_y = int(npc.blit_pos[1])

        # Position bubble above head; clamp to stay on screen
        bubble_x = max(4, min(head_x - bubble_w // 2, WIDTH - bubble_w - 4))
        bubble_y = max(4, head_y - TAIL_H - bubble_h)

        bubble_rect = pg.Rect(bubble_x, bubble_y, bubble_w, bubble_h)
        pg.draw.rect(self.screen, BG, bubble_rect, border_radius=10)
        pg.draw.rect(self.screen, BORDER, bubble_rect, 2, border_radius=10)

        # Tail pointing down toward the NPC's head
        # Clamp tail tip x so it stays inside the bubble footprint
        tail_cx = max(bubble_x + TAIL_W + 4, min(head_x, bubble_x + bubble_w - TAIL_W - 4))
        tail_top_y = bubble_y + bubble_h
        tail_tip_y = tail_top_y + TAIL_H
        tail_pts = [
            (tail_cx - TAIL_W, tail_top_y),
            (tail_cx + TAIL_W, tail_top_y),
            (tail_cx, tail_tip_y),
        ]
        pg.draw.polygon(self.screen, BG, tail_pts)
        pg.draw.line(self.screen, BORDER,
                     (tail_cx - TAIL_W, tail_top_y), (tail_cx, tail_tip_y), 2)
        pg.draw.line(self.screen, BORDER,
                     (tail_cx + TAIL_W, tail_top_y), (tail_cx, tail_tip_y), 2)

        # Text
        for i, line in enumerate(lines):
            surf = font.render(line, True, TEXT_COLOR)
            self.screen.blit(surf, (bubble_x + PADDING, bubble_y + PADDING + i * line_h))

    def draw_ammo(self):
        bar_h = self.status_bar.get_height()
        bar_w = self.status_bar.get_width()
        bar_x = H_WIDTH - bar_w // 2
        large = self.ammo_glyphs['large']
        small = self.ammo_glyphs['small']
        # fall back to STTNUM if AMMNUM not in the WAD
        large_glyphs = large if large else self.hud_numbers

        # Current weapon ammo — right-aligned to ~18.5% of bar width (matches Doom layout)
        ammo_type = WEAPON_AMMO_TYPE.get(self.player.current_weapon)
        if ammo_type and large_glyphs:
            text = str(self.player.ammo[ammo_type])
            glyphs = [large_glyphs.get(ch) for ch in text if large_glyphs.get(ch)]
            if glyphs:
                right_edge = bar_x + int(bar_w * 0.185)
                total_w = sum(g.get_width() for g in glyphs)
                x = right_edge - total_w
                glyph_h = glyphs[0].get_height()
                y = HEIGHT - bar_h + (bar_h - glyph_h) // 2
                for glyph in glyphs:
                    self.screen.blit(glyph, (x, y))
                    x += glyph.get_width()

        # Four ammo-type counters — small gray STGNUM digits, right of status bar
        if small:
            row_h = bar_h // 4
            glyph_h = next(iter(small.values())).get_height()
            for i, atype in enumerate(('bullets', 'shells', 'rockets', 'cells')):
                x = bar_x + int(bar_w * 0.865)
                y = HEIGHT - bar_h + i * row_h + (row_h - glyph_h) // 2
                for ch in str(self.player.ammo[atype]):
                    glyph = small.get(ch)
                    if glyph:
                        self.screen.blit(glyph, (x, y))
                        x += glyph.get_width()

    def draw_armor(self):
        bar_h = self.status_bar.get_height()
        bar_x = H_WIDTH - self.status_bar.get_width() // 2
        x = bar_x + int(self.status_bar.get_width() * 0.59)
        for ch in f'{max(0, self.player.armor)}%':
            glyph = self.hud_numbers.get(ch)
            if glyph:
                y = HEIGHT - bar_h + (bar_h - glyph.get_height()) // 2
                self.screen.blit(glyph, (x, y))
                x += glyph.get_width()

    def draw_armor_tint(self):
        elapsed = pg.time.get_ticks() - self.player.armor_pickup_time
        alpha = int(100 * max(0, 1 - elapsed / self.player.ARMOR_TINT_DURATION))
        if alpha <= 0:
            return
        tint = pg.Surface((WIDTH, HEIGHT), pg.SRCALPHA)
        tint.fill((0, 200, 0, alpha))
        self.screen.blit(tint, (0, 0))

    def draw_health_tint(self):
        elapsed = pg.time.get_ticks() - self.player.health_pickup_time
        alpha = int(100 * max(0, 1 - elapsed / self.player.HEALTH_TINT_DURATION))
        if alpha <= 0:
            return
        tint = pg.Surface((WIDTH, HEIGHT), pg.SRCALPHA)
        tint.fill((0, 100, 200, alpha))
        self.screen.blit(tint, (0, 0))

    def draw_pain_tint(self):
        if not self.player.is_in_pain:
            return
        elapsed = pg.time.get_ticks() - self.player.pain_start_time
        alpha = int(140 * max(0, 1 - elapsed / self.player.PAIN_DURATION))
        if alpha <= 0:
            return
        tint = pg.Surface((WIDTH, HEIGHT), pg.SRCALPHA)
        tint.fill((200, 0, 0, alpha))
        self.screen.blit(tint, (0, 0))

    # draw the doomguy's face on the status bar.
    def draw_doomguy(self, sprite_name='STFST00'):
        img = self.doomguy[sprite_name]
        pos = (H_WIDTH - img.get_width() //2,HEIGHT - img.get_height() )
        self.screen.blit(img, pos)

    def debug_cursor_control(self):
        # if in debug mode, disable all movement
        if not self.engine.debug_mode:
            return
        speed = 0.5 * self.engine.dt

        key_state = pg.key.get_pressed()
        inc = vec2(0)
        if key_state[pg.K_LEFT]:
            inc += vec2(-speed,0)
        if key_state[pg.K_RIGHT]:
            inc += vec2(speed,0)
        if key_state[pg.K_UP]:
            inc += vec2(0, -speed)
        if key_state[pg.K_DOWN]:
            inc += vec2(0,speed)
        if inc.x and inc.y:
            inc *= 1/math.sqrt(2)
        self.debug_cursor = (self.debug_cursor[0] + inc.x, self.debug_cursor[1] + inc.y)

    def draw_debug_cursor(self):
        """
        for debugging
        """
        pg.draw.line(self.engine.screen, (255,0,0), (self.debug_cursor[0], 0), (self.debug_cursor[0], HEIGHT), 3)
        pg.draw.line(self.engine.screen, (255,0,0), (0, self.debug_cursor[1]), (WIDTH, self.debug_cursor[1]), 3)
        pg.draw.circle(self.engine.screen, 'red', (self.debug_cursor), 4)


    def draw_z_buffer(self):
        """
        For debugging
        """
        zb = self.z_buffer.copy()
        zb[np.isinf(zb)] = 999.

        # normalize to 0..255
        max_depth = np.max(zb)
        norm = (zb / max_depth) * 255
        # invert
        norm = 255 - norm
        img = norm.astype(np.uint8)
        rgb = np.repeat(img[:,:, None], 3, axis=2)
        surf = pg.surfarray.make_surface(rgb)
        self.screen.blit(surf, (0,0))

    @staticmethod
    @njit
    def draw_column(framebuffer, x, y1, y2, colour):
        for iy in range(y1, y2+1):
            framebuffer[x, iy] = colour


    @staticmethod
    @njit(fastmath=True)
    def draw_wall_col(framebuffer, tex, tex_col, x, y1, y2, tex_alt, inv_scale, light_level):
        if y1 < y2:
            tex_w, tex_h = len(tex), len(tex[0])
            tex_col = int(tex_col) % tex_w
            tex_y = tex_alt + (float(y1) - H_HEIGHT) * inv_scale

            for iy in range(y1, y2 + 1):
                col = tex[tex_col, int(tex_y) % tex_h]
                col = col[0] * light_level, col[1] * light_level, col[2] * light_level
                framebuffer[x, iy] = col
                tex_y += inv_scale

    @staticmethod
    @njit(fastmath=True)
    def draw_flat_col(screen, flat_tex, x, y1, y2, light_level, world_z,
                      player_angle, player_x, player_y, z_col):
        player_dir_x = math.cos(math.radians(player_angle))
        player_dir_y = math.sin(math.radians(player_angle))

        for i, iy in enumerate(range(y1, y2 + 1)):
            z = H_WIDTH * world_z / (H_HEIGHT - iy)
            z_col[i] = z  # store the depth in the z-buffer

            px = player_dir_x * z + player_x
            py = player_dir_y * z + player_y

            left_x = -player_dir_y * z + px
            left_y = player_dir_x * z + py
            right_x = player_dir_y * z + px
            right_y = -player_dir_x * z + py

            dx = (right_x - left_x) / WIDTH
            dy = (right_y - left_y) / WIDTH

            tx = int(left_x + dx * x) & 63
            ty = int(left_y + dy * x) & 63

            col = flat_tex[tx, ty]
            col = col[0] * light_level, col[1] * light_level, col[2] * light_level
            screen[x, iy] = col