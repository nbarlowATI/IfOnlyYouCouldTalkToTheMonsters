import sys
import pygame as pg

from wad_data import WADData
from map_renderer import MapRenderer
from player import Player
from bsp import BSP
from object_handler import ObjectHandler
from raycasting import RayCasting
from seg_handler import SegHandler
from sounds import SoundEffect
from view_renderer import ViewRenderer
from weapon import Weapon

from events import *
from doomsettings import *


class DoomEngine:
    def __init__(self, wad_path="wad/DOOM1.wad"):
        self.map_mode = False
        self.debug_mode = False
        self.talk_mode = False
        self.talk_text = ""
        self.npc_response_npc = None    # NPC currently "speaking"
        self.npc_response_words = []    # full response split into words
        self.npc_words_shown = 0        # how many words revealed so far
        self.npc_word_time = 0          # timestamp of last word reveal
        self.NPC_WORD_INTERVAL = 200    # ms between each word appearing
        self.NPC_TALK_RANGE = 600       # world units
        self.last_enter_time = 0        # for double-Enter detection
        self.DOUBLE_ENTER_MS = 400      # max gap between two Enters to count as double
        self.wad_path = wad_path
        self.screen = pg.display.set_mode(WIN_RES, pg.SCALED)
        self.framebuffer = pg.surfarray.array3d(self.screen)
        pg.mouse.set_visible(False)
        self.clock = pg.time.Clock()
        self.running = True
        self.dt = 1 / 60

    def load(self, map_name="E1M1", difficulty=1):
        self.wad_data = WADData(self, map_name)
        self.map_renderer = MapRenderer(self)
        self.player = Player(self)
        
        self.bsp = BSP(self)
        self.raycaster = RayCasting(self)
        self.seg_handler = SegHandler(self)
        self.view_renderer = ViewRenderer(self)
        self.object_handler = ObjectHandler(self)
        self.object_handler.add_objects_npcs(difficulty)
        self.weapon = Weapon(self)
        self.doors = {}
        # set timer to change doomguy face every 2s
        pg.time.set_timer(DOOMGUY_FACE_CHANGE_EVENT, 2000)

    def update(self):
        # reset view renderer's clip buffers, used to correctly occlude sprites
        self.view_renderer.reset_clip_buffers()
        self.player.update()
        self.weapon.update()
        self.seg_handler.update()
        self.bsp.update()
        for door in self.doors.values():
            door.update()
        self.object_handler.update()
        self.view_renderer.update()
        # Advance NPC response word by word
        if self.npc_response_npc is not None:
            from npc import NPCState
            if self.npc_response_npc.state in (NPCState.dead, NPCState.dying):
                self.npc_response_npc = None
            elif self.npc_words_shown < len(self.npc_response_words):
                now = pg.time.get_ticks()
                if now - self.npc_word_time >= self.NPC_WORD_INTERVAL:
                    self.npc_words_shown += 1
                    self.npc_word_time = now
                    if self.npc_words_shown % 2 == 0 and self.npc_response_npc.pain_sound:
                        self.npc_response_npc.pain_sound.play_random_pitch()
        self.dt = self.clock.tick()
        pg.display.set_caption(f"{self.clock.get_fps()}")
        

    def draw(self):
        if self.map_mode:
            pg.display.flip()  # put flip here for debug draw
            self.screen.fill('black')
            self.map_renderer.draw()
        else:
            pg.surfarray.blit_array(self.screen, self.framebuffer)
            
            for npc in self.object_handler.npcs:
                self.view_renderer.draw_sprite(npc)
            for obj in self.object_handler.objects:
                self.view_renderer.draw_sprite(obj)
            for proj in self.object_handler.projectiles:
                self.view_renderer.draw_sprite(proj)
            
            self.view_renderer.draw_pain_tint()
            self.view_renderer.draw_weapon()
            self.view_renderer.draw_status_bar()
            self.view_renderer.draw_doomguy(self.player.face_img)
            self.view_renderer.draw_health()
            if self.talk_mode:
                self.view_renderer.draw_talk_bubble(self.talk_text)
            if self.npc_response_npc is not None:
                displayed = ' '.join(self.npc_response_words[:self.npc_words_shown])
                self.view_renderer.draw_npc_bubble(self.npc_response_npc, displayed)
            if self.debug_mode:
                self.view_renderer.draw_z_buffer()
                self.view_renderer.draw_debug_cursor()
            pg.display.flip()  

    def check_events(self):
        for e in pg.event.get():
            if e.type == pg.QUIT or (e.type == pg.KEYDOWN and e.key == pg.K_ESCAPE):
                self.running = False
            if e.type == pg.KEYDOWN:
                # T enters talk mode
                if e.key == pg.K_t and not self.talk_mode:
                    self.talk_mode = True
                # Text input while in talk mode
                elif self.talk_mode:
                    if e.key == pg.K_RETURN:
                        now = pg.time.get_ticks()
                        double_press = (now - self.last_enter_time) < self.DOUBLE_ENTER_MS
                        self.last_enter_time = now
                        if double_press:
                            # Double-Enter always exits talk mode
                            self.talk_mode = False
                            self.talk_text = ""
                            self.npc_response_npc = None
                        else:
                            # Find nearest NPC within talk range
                            nearest_npc = None
                            nearest_dist = self.NPC_TALK_RANGE
                            for npc in self.object_handler.npcs:
                                d = (npc.pos - self.player.pos).magnitude()
                                if d < nearest_dist:
                                    nearest_dist = d
                                    nearest_npc = npc
                            if nearest_npc:
                                # Clear player bubble; start NPC word-by-word response
                                self.talk_text = ""
                                response = "This is a test. This is a test."
                                self.npc_response_npc = nearest_npc
                                self.npc_response_words = response.split()
                                self.npc_words_shown = 0
                                self.npc_word_time = pg.time.get_ticks()
                            else:
                                # No NPC nearby — exit talk mode normally
                                self.talk_mode = False
                                self.talk_text = ""
                                self.npc_response_npc = None
                    elif e.key == pg.K_BACKSPACE:
                        self.talk_text = self.talk_text[:-1]
                    elif e.unicode and e.unicode.isprintable():
                        # Player started typing — dismiss any NPC response
                        self.npc_response_npc = None
                        self.talk_text += e.unicode
                else:
                    if e.key == pg.K_SPACE:
                        self.player.handle_action()
                    elif pg.K_0 <= e.key <= pg.K_9:
                        self.player.change_weapon(chr(e.key))
                    # print some debug output
                    elif e.key == pg.K_n:
                        cursor_x = int(self.view_renderer.debug_cursor[0])
                        cursor_y = int(self.view_renderer.debug_cursor[1])
                        z_val = self.view_renderer.z_buffer[cursor_x, cursor_y]
                        print(f"z-buffer {(cursor_x,cursor_y)} {z_val}")
                        barrel_dists = []
                        for obj in self.object_handler.objects:
                            if obj.sprite_name_base == "BAR1" and obj.dist:
                                barrel_dists.append(obj.dist)
                        if len(barrel_dists) > 0:
                            print(f"Distance to nearest barrel {min(barrel_dists)}")
                    elif e.key == pg.K_m:
                        self.map_mode = not self.map_mode
                    elif e.key == pg.K_b:
                        if not self.map_mode:
                            self.debug_mode = not self.debug_mode
            # cycle randomly through the different doomguy faces
            if e.type == DOOMGUY_FACE_CHANGE_EVENT:
                self.player.set_face_image()
            # fire weapon (disabled in talk mode)
            if e.type == pg.MOUSEBUTTONDOWN and not self.talk_mode:
                self.player.handle_fire_event(e)


    def run(self):
        while self.running:
            self.update()
            self.check_events()
            self.draw()
        pg.quit()
        sys.exit()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        map = sys.argv[1]
    else:
        map = "E1M1"
    if len(sys.argv) > 2:
        difficulty = int(sys.argv[2])
    else:
        difficulty = 1
    game = DoomEngine()
    game.load(map, difficulty)
    game.run()
        