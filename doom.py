import sys
import json
import random
import threading
import pygame as pg

from wad_data import WADData
from map_renderer import MapRenderer
from player import Player
from bsp import BSP
from object_handler import ObjectHandler
from raycasting import RayCasting
from seg_handler import SegHandler
from view_renderer import ViewRenderer
from weapon import Weapon

from events import *
from doomsettings import *
from talk import Talk


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
        self.talk_engine = Talk()
        self._response_queue = []       # filled by background threads: (npc, text, delta, player_text)
        self.screen = pg.display.set_mode(WIN_RES, pg.SCALED)
        self.framebuffer = pg.surfarray.array3d(self.screen)
        pg.mouse.set_visible(False)
        self.clock = pg.time.Clock()
        self.running = True
        self.dt = 1 / 60

    def load(self, map_name="E1M1", difficulty=1):
        self.map_name = map_name
        self.difficulty = difficulty
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
        # Process completed LLM responses from background threads
        while self._response_queue:
            npc, text, delta, player_text = self._response_queue.pop(0)
            npc.waiting_for_llm = False
            from npc import NPCState
            if npc.state not in (NPCState.dead, NPCState.dying):
                npc.conversation_history.append({"player": player_text, "npc": text})
                npc.friendliness = max(0, min(100, npc.friendliness + delta))
                print(f"{npc.npc_name} friendliness: {npc.friendliness} (delta: {delta:+d})")
                if npc.friendliness >= 60:
                    level_friends = self.player.friends.setdefault(self.map_name, [])
                    entry = {"name": npc.npc_name, "species": npc.species}
                    if entry not in level_friends:
                        level_friends.append(entry)
                        print(f"New friend: {npc.npc_name} ({npc.species}) in {self.map_name}")
                if self.npc_response_npc is npc:
                    self.npc_response_words = text.split()
                    self.npc_words_shown = 0
                    self.npc_word_time = pg.time.get_ticks()

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
            elif self.npc_response_npc.friendliness <= 0:
                # All words shown and NPC is now fully hostile — force-exit talk mode
                self.talk_mode = False
                self.talk_text = ""
                self.npc_response_npc = None
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
            
            self.view_renderer.draw_armor_tint()
            self.view_renderer.draw_health_tint()
            self.view_renderer.draw_pain_tint()
            self.view_renderer.draw_weapon()
            self.view_renderer.draw_status_bar()
            self.view_renderer.draw_doomguy(self.player.face_img)
            self.view_renderer.draw_health()
            self.view_renderer.draw_armor()
            self.view_renderer.draw_ammo()
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
                            if nearest_npc and not nearest_npc.waiting_for_llm:
                                player_text = self.talk_text
                                self.talk_text = ""
                                self.npc_response_npc = nearest_npc
                                self.npc_response_words = ["..."]
                                self.npc_words_shown = 1
                                self.npc_word_time = pg.time.get_ticks()
                                nearest_npc.waiting_for_llm = True
                                threading.Thread(
                                    target=self._fetch_npc_response,
                                    args=(nearest_npc, player_text),
                                    daemon=True,
                                ).start()
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


    def _fetch_npc_response(self, npc, player_text):
        context = npc.get_character_context()
        history_lines = []
        for turn in npc.conversation_history:
            history_lines.append(f"Player: {turn['player']}")
            history_lines.append(f"{npc.npc_name}: {turn['npc']}")
        history_lines.append(f"Player: {player_text}")
        conversation = "\n".join(history_lines)
        try:
            raw = self.talk_engine.get_response(context, conversation)
            data = json.loads(raw.message.content)
            text = data.get('text', '')
            player_score = int(data.get('player_score', 0))
            delta = int(data.get('friendliness_delta', 0))
            print(f"  player_score: {player_score:+d}")
        except Exception as e:
            print(f"LLM response error: {e}")
            print(f"Raw response content: {repr(raw.message.content)}")
            text = "..."
            delta = 0
        self._response_queue.append((npc, text, delta, player_text))

    def _play_wad_sound(self, lump_name):
        import io, wave
        from wad_reader import WADReader
        reader = WADReader(self.wad_path)
        try:
            for entry in reader.directory:
                if entry['lump_name'].upper() == lump_name.upper():
                    reader.wad_file.seek(entry['lump_offset'])
                    raw = reader.wad_file.read(entry['lump_size'])
                    num_samples = raw[1] + (raw[2] << 8)
                    samples = raw[8:8 + num_samples]
                    buf = io.BytesIO()
                    with wave.open(buf, 'wb') as wf:
                        wf.setnchannels(1)
                        wf.setsampwidth(1)
                        wf.setframerate(SAMPLE_RATE)
                        wf.writeframes(samples)
                    buf.seek(0)
                    pg.mixer.init()
                    pg.mixer.Sound(buf).play()
                    break
        finally:
            reader.close()

    def _melt_transition(self, from_surf):
        """Classic DOOM melt wipe: columns slide down at staggered speeds."""
        COLS = DOOM_W  # 320 columns
        col_w = WIDTH // COLS  # pixels per column (= SCALE = 4)

        # Initialise column offsets: y[i] < 0 means delayed start,
        # y[i] >= 0 means the column has shifted that many pixels down.
        y = [0] * COLS
        y[0] = -(random.randint(0, 15))
        for i in range(1, COLS):
            y[i] = max(-15, min(0, y[i - 1] + random.randint(-1, 1)))

        clock = pg.time.Clock()
        while True:
            for e in pg.event.get():
                if e.type == pg.QUIT:
                    self.running = False
                    return

            self.screen.fill('black')
            all_done = True
            for i in range(COLS):
                x = i * col_w
                if y[i] < 0:
                    y[i] += 1
                    all_done = False
                    # Column hasn't started melting — draw it in place
                    self.screen.blit(from_surf, (x, 0), pg.Rect(x, 0, col_w, HEIGHT))
                elif y[i] < HEIGHT:
                    all_done = False
                    dy = (y[i] + 1) if y[i] < 16 else 8
                    y[i] = min(HEIGHT, y[i] + dy)
                    # Draw the column shifted downward; black shows above it
                    remaining = HEIGHT - y[i]
                    if remaining > 0:
                        self.screen.blit(from_surf, (x, y[i]), pg.Rect(x, 0, col_w, remaining))

            pg.display.flip()
            clock.tick(70)  # 2× original DOOM tic rate
            if all_done:
                break

    def trigger_level_exit(self, seg):
        # Flip switch texture: EXIT1→EXIT2, SW1xxx→SW2xxx
        # Check both sidedefs and all texture slots
        activated = False
        for sidedef in (seg.linedef.front_sidedef, seg.linedef.back_sidedef):
            if sidedef is None:
                continue
            for attr in ('middle_texture', 'upper_texture', 'lower_texture'):
                tex = getattr(sidedef, attr)
                if tex and tex.startswith('SW1'):
                    target = 'SW2' + tex[3:]
                    print(f"[SWITCH] {attr}={tex!r} -> {target!r}  target_in_textures={target in self.wad_data.asset_data.textures}")
                    setattr(sidedef, attr, target)
                    activated = True
                elif tex == 'EXIT1':
                    setattr(sidedef, attr, 'EXIT2')
                    activated = True
                else:
                    print(f"[SWITCH] sidedef {attr}={tex!r}  in_textures={tex in self.wad_data.asset_data.textures}")
        if not activated:
            print("[SWITCH] no matching texture found — no visual change")
        # Play switch sound, re-render so the new texture is in the framebuffer, then pause
        from sounds import SoundEffect
        switch_sound = SoundEffect('DSSWTCHN', self)
        switch_sound.play()
        self.view_renderer.reset_clip_buffers()
        self.seg_handler.update()
        self.bsp.update()
        self.draw()
        pg.time.wait(800)
        current = self.screen.copy()
        self._melt_transition(current)
        next_map = self._show_intermission()
        if self.running and next_map:
            self.load(next_map, self.difficulty)

    def _next_map(self):
        ep = int(self.map_name[1])
        mn = int(self.map_name[3])
        if mn < 8:
            return f"E{ep}M{mn + 1}"
        return f"E{ep + 1}M1" if ep < 3 else None

    def _show_intermission(self):
        next_map = self._next_map()
        assets = self.wad_data.asset_data.intermission

        bg_raw = assets.get('background')
        bg = pg.transform.scale(bg_raw, WIN_RES) if bg_raw else None

        ep = int(self.map_name[1])
        mn = int(self.map_name[3])
        finished_img  = assets.get(f'WILV{ep - 1}{mn - 1}')
        enter_label   = assets.get('entering')
        entering_img  = None
        if next_map:
            nep, nmn = int(next_map[1]), int(next_map[3])
            entering_img = assets.get(f'WILV{nep - 1}{nmn - 1}')

        hud_font = self.wad_data.asset_data.hud_font
        n_friends = len(self.player.friends.get(self.map_name, []))
        friends_text = f"FRIENDS MADE: {n_friends}"

        while self.running:
            for e in pg.event.get():
                if e.type == pg.QUIT or (e.type == pg.KEYDOWN and e.key == pg.K_ESCAPE):
                    self.running = False
                    return None
                if e.type in (pg.KEYDOWN, pg.MOUSEBUTTONDOWN):
                    self._melt_transition(self.screen.copy())
                    return next_map

            self.screen.blit(bg, (0, 0))

            y = HEIGHT // 6
            if finished_img:
                x = (WIDTH - finished_img.get_width()) // 2
                self.screen.blit(finished_img, (x, y))
                y += finished_img.get_height() + 10

            SPACE_W = 16
            glyphs = [(hud_font[ch] if ch in hud_font else None) for ch in friends_text]
            total_w = sum(g.get_width() if g else SPACE_W for g in glyphs)
            glyph_h = next((g.get_height() for g in glyphs if g), 0)
            x = (WIDTH - total_w) // 2
            for g in glyphs:
                if g:
                    self.screen.blit(g, (x, y))
                    x += g.get_width()
                else:
                    x += SPACE_W
            y += glyph_h + 10

            y = HEIGHT * 2 // 3
            if enter_label:
                x = (WIDTH - enter_label.get_width()) // 2
                self.screen.blit(enter_label, (x, y))
                y += enter_label.get_height() + 10
            if entering_img:
                x = (WIDTH - entering_img.get_width()) // 2
                self.screen.blit(entering_img, (x, y))

            pg.display.flip()
            self.clock.tick(60)
        return None

    def show_title_screen(self):
        img = pg.image.load('assets/title_screen.png')
        img = pg.transform.scale(img, WIN_RES)
        while self.running:
            for e in pg.event.get():
                if e.type == pg.QUIT or (e.type == pg.KEYDOWN and e.key == pg.K_ESCAPE):
                    self.running = False
                    return
                if e.type in (pg.KEYDOWN, pg.MOUSEBUTTONDOWN):
                    self._play_wad_sound('DSPISTOL')
                    self._melt_transition(img)
                    return
            self.screen.blit(img, (0, 0))
            pg.display.flip()
            self.clock.tick(60)

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
        difficulty = int(sys.argv[2]) if len(sys.argv) > 2 else 1
        game = DoomEngine()
        game.load(map, difficulty)
        game.run()
    else:
        game = DoomEngine()
        game.show_title_screen()
        if game.running:
            game.load("E1M1", 1)
            game.run()
        