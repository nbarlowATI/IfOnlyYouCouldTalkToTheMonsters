import math
import numpy as np
from doomsettings import *

class SegHandler:
    MAX_SCALE = 64.0
    MIN_SCALE = 0.00390625

    def __init__(self, engine):
        self.engine = engine
        self.wad_data = engine.wad_data
        self.player = engine.player
        self.framebuffer = engine.framebuffer
        self.textures = self.wad_data.asset_data.textures
        self.sky_id = self.wad_data.asset_data.sky_id
        self.seg = None
        self.rw_angle1 = None
        self.screen_range: set = None
        self.x_to_angle = self.get_x_to_angle_table()
        self.upper_clip, self.lower_clip = [], []

    def update(self):
        self.init_floor_ceil_clip_height()
        self.init_screen_range()

    def init_floor_ceil_clip_height(self):
        self.upper_clip = [-1 for _ in range(WIDTH)]
        self.lower_clip = [HEIGHT for _ in range(WIDTH)]


    @staticmethod
    def get_x_to_angle_table():
        x_to_angle = []
        for i in range(0, WIDTH +1):
            angle = math.degrees(math.atan((H_WIDTH -i) / SCREEN_DIST))
            x_to_angle.append(angle)
        return x_to_angle
    
    def scale_from_global_angle(self, x, rw_normal_angle, rw_distance):
        x_angle = self.x_to_angle[x]
        num = SCREEN_DIST * math.cos(math.radians(rw_normal_angle - x_angle - self.player.angle))
        den = rw_distance * math.cos(math.radians(x_angle))

        scale = num / den
        scale = min(self.MAX_SCALE, max(self.MIN_SCALE, scale))
        return scale


    def draw_solid_wall_range(self, x1, x2):
        seg=self.seg
        front_sector = seg.front_sector
        line = seg.linedef
        side = line.front_sidedef
        renderer = self.engine.view_renderer
        upper_clip = self.upper_clip
        lower_clip = self.lower_clip
        framebuffer = self.framebuffer

        wall_texture_id = side.middle_texture
        ceil_texture_id = front_sector.ceil_texture
        floor_texture_id = front_sector.floor_texture
        light_level = front_sector.light_level

        world_front_z1 = front_sector.ceil_height - self.player.view_height
        world_front_z2 = front_sector.floor_height - self.player.view_height

        # check which parts to render
        b_draw_wall = side.middle_texture != '-'
        b_draw_ceil = world_front_z1 > 0
        b_draw_floor = world_front_z2 < 0

        # Wall segment vector and length in world space
        wall_dx = seg.end_vertex[0] - seg.start_vertex[0]
        wall_dy = seg.end_vertex[1] - seg.start_vertex[1]
        wall_len = math.hypot(wall_dx, wall_dy)
        wall_dir = (wall_dx / wall_len, wall_dy / wall_len)

        # calculate scaling factors for left and right edges of the wall range
        rw_normal_angle = seg.angle + 90
        offset_angle = rw_normal_angle - self.rw_angle1

        hypoteneuse = math.dist(self.player.pos, seg.start_vertex)
        rw_distance = hypoteneuse * math.cos(math.radians(offset_angle))
        rw_scale1 = self.scale_from_global_angle(x1, rw_normal_angle, rw_distance)

        if math.isclose(offset_angle % 360, 90, abs_tol=1):
            rw_scale1 *= 0.01

        if x1 < x2:
            scale2 = self.scale_from_global_angle(x2, rw_normal_angle, rw_distance)
            rw_scale_step = (scale2 - rw_scale1) / (x2 - x1)
        else:
            rw_scale_step = 0

        # determine how the wall texture are vertically aligned
        wall_texture = self.textures[wall_texture_id]
        if line.flags & self.wad_data.LINEDEF_FLAGS['DONT_PEG_BOTTOM']:
            v_top = front_sector.floor_height + wall_texture.shape[1]
            middle_tex_alt = v_top - self.player.view_height
        else:
            middle_tex_alt = world_front_z1
        middle_tex_alt += side.y_offset

        # determine how the wall textures are horizontally aligned
        rw_offset = hypoteneuse * math.sin(math.radians(offset_angle))
        rw_offset += seg.offset + side.x_offset
        rw_center_angle = rw_normal_angle - self.player.angle

        # determine where on the screen the wall is drawn:
        wall_y1 = H_HEIGHT - world_front_z1 * rw_scale1
        wall_y1_step = -rw_scale_step * world_front_z1
        wall_y2 = H_HEIGHT - world_front_z2 * rw_scale1
        wall_y2_step = -rw_scale_step * world_front_z2

        # player position
        player_x, player_y = self.player.pos

        # render loop
        for x in range(x1, x2+1):
            draw_wall_y1 = wall_y1 - 1
            draw_wall_y2 = wall_y2
            # Update clipping buffers

            if b_draw_ceil:
                cy1 = upper_clip[x] + 1
                cy2 = int(min(draw_wall_y1 - 1, lower_clip[x] - 1))
                renderer.draw_flat(ceil_texture_id, light_level, x, cy1, cy2, world_front_z1)

            if b_draw_wall:
                wy1 = int(max(draw_wall_y1, upper_clip[x] + 1))
                wy2 = int(min(draw_wall_y2, lower_clip[x] -1))
                if wy1 < wy2:
                    angle = rw_center_angle - self.x_to_angle[x]
                    # Get horizontal distance along wall from texture coordinate logic
                    wall_offset_along = rw_distance * math.tan(math.radians(angle)) - rw_offset 
                    # Convert wall offset to wall/ray intersection world coords
                    intersect_x = seg.start_vertex[0] + wall_dir[0] * wall_offset_along
                    intersect_y = seg.start_vertex[1] + wall_dir[1] * wall_offset_along
                    # Raw distance from player to intersection
                    hit_dist = math.hypot(intersect_x - player_x, intersect_y - player_y)                
                    inv_scale = 1.0 / rw_scale1
                    # update wall_depth buffer
                    renderer.z_buffer[x, wy1:wy2] = hit_dist
                    renderer.draw_wall_col(
                        framebuffer, wall_texture, wall_offset_along, x, wy1, wy2,
                        middle_tex_alt, inv_scale, light_level,
                    )
                
            if b_draw_floor:
                fy1 = int(max(draw_wall_y2 + 1, upper_clip[x] + 1))
                fy2 = lower_clip[x] -1
                renderer.draw_flat(floor_texture_id, light_level, x, fy1, fy2, world_front_z2)

            rw_scale1 += rw_scale_step
            wall_y1 += wall_y1_step
            wall_y2 += wall_y2_step

    def draw_portal_wall_range(self, x1, x2):
        seg = self.seg
        front_sector = seg.front_sector
        back_sector = seg.back_sector
        line = seg.linedef
        side = line.front_sidedef
        renderer = self.engine.view_renderer
        upper_clip = self.upper_clip
        lower_clip = self.lower_clip
        framebuffer = self.framebuffer

        upper_wall_texture = side.upper_texture
        lower_wall_texture = side.lower_texture
        tex_ceil_id = front_sector.ceil_texture
        tex_floor_id = front_sector.floor_texture
        light_level = front_sector.light_level

        player_x, player_y = self.player.pos

        # Wall segment vector and length in world space
        wall_dx = seg.end_vertex[0] - seg.start_vertex[0]
        wall_dy = seg.end_vertex[1] - seg.start_vertex[1]
        wall_len = math.hypot(wall_dx, wall_dy)
        wall_dir = (wall_dx / wall_len, wall_dy / wall_len)

        # calculate relative plane heights of front and back sector
        world_front_z1 = front_sector.ceil_height - self.player.view_height
        world_back_z1 = back_sector.ceil_height - self.player.view_height
        world_front_z2 = front_sector.floor_height - self.player.view_height
        world_back_z2 = back_sector.floor_height - self.player.view_height

        # sky hack
        if front_sector.ceil_texture == back_sector.ceil_texture == self.sky_id:
            world_front_z1 = world_back_z1

        # choose which parts to render
        if (world_front_z1 != world_back_z1 or
            front_sector.light_level != back_sector.light_level or
            front_sector.ceil_texture != back_sector.ceil_texture):
            b_draw_upper_wall = side.upper_texture != '-' and world_back_z1 < world_front_z1
            b_draw_ceil = world_front_z1 >= 0
        else:
            b_draw_upper_wall = False
            b_draw_ceil = False

        if (world_front_z2 != world_back_z2 or 
            front_sector.floor_texture != back_sector.floor_texture or
            front_sector.light_level != back_sector.light_level):
            b_draw_lower_wall = side.lower_texture != '-' and world_back_z2 > world_front_z2
            b_draw_floor = world_front_z2 <= 0
        else:
            b_draw_lower_wall = False
            b_draw_floor = False
        
        # if nothing to be rendered, return early
        if (not b_draw_upper_wall and not b_draw_ceil and not b_draw_lower_wall and not b_draw_floor):
            return None
        # calculate scaling factors of left and right edges
        rw_normal_angle = seg.angle + 90
        offset_angle = rw_normal_angle - self.rw_angle1

        hypoteneuse = math.dist(self.player.pos, seg.start_vertex)
        rw_distance = hypoteneuse * math.cos(math.radians(offset_angle))

        rw_scale1 = self.scale_from_global_angle(x1, rw_normal_angle, rw_distance)
        if math.isclose(offset_angle % 360, 90, abs_tol=1):
            rw_scale1 *= 0.01
        if x2 > x1:
            scale2 = self.scale_from_global_angle(x2, rw_normal_angle, rw_distance)
            rw_scale_step = (scale2 - rw_scale1) / (x2 - x1)
        else:
            rw_scale_step = 0

        # determine how the wall textures are vertically aligned
        if b_draw_upper_wall:
            upper_wall_texture = self.textures[side.upper_texture]

            if line.flags & self.wad_data.LINEDEF_FLAGS['DONT_PEG_TOP']:
                upper_tex_alt = world_front_z1
            else:
                v_top = back_sector.ceil_height + upper_wall_texture.shape[1]
                upper_tex_alt = v_top - self.player.view_height
            upper_tex_alt += side.y_offset

        if b_draw_lower_wall:
            lower_wall_texture = self.textures[side.lower_texture]

            if line.flags & self.wad_data.LINEDEF_FLAGS['DONT_PEG_BOTTOM']:
                lower_tex_alt = world_front_z1
            else:
                lower_tex_alt = world_back_z2
            lower_tex_alt += side.y_offset

        # determine how the wall textures are horizontally aligned
        if seg_textured:= b_draw_upper_wall or b_draw_lower_wall:
            rw_offset = hypoteneuse * math.sin(math.radians(offset_angle))
            rw_offset += seg.offset + side.x_offset
            
            rw_center_angle = rw_normal_angle - self.player.angle


        # y positions of the top/bottom edges on the screen
        wall_y1 = H_HEIGHT - world_front_z1 * rw_scale1
        wall_y1_step = -rw_scale_step * world_front_z1
        wall_y2 = H_HEIGHT - world_front_z2 * rw_scale1
        wall_y2_step = -rw_scale_step * world_front_z2

        # the y position of the top edge of the portal
        if b_draw_upper_wall:
            if world_back_z1 > world_front_z2:
                portal_y1 = H_HEIGHT - world_back_z1 * rw_scale1
                portal_y1_step = -rw_scale_step * world_back_z1
            else:
                portal_y1 = wall_y2
                portal_y1_step = wall_y2_step

        if b_draw_lower_wall:
            if world_back_z2 < world_front_z1:
                portal_y2 = H_HEIGHT - world_back_z2 * rw_scale1
                portal_y2_step = -rw_scale_step * world_back_z2
            else:
                portal_y2 = wall_y1
                portal_y2_step = wall_y1_step

        upper_clip = self.upper_clip
        lower_clip = self.lower_clip

        # rendering 
        for x in range(x1, x2 + 1):
            draw_wall_y1 = wall_y1 - 1
            draw_wall_y2 = wall_y2
            # for z_buffer
            hit_dist = np.inf

            if seg_textured:
                angle = rw_center_angle - self.x_to_angle[x]
                wall_offset_along = rw_distance * math.tan(math.radians(angle)) - rw_offset
                # Convert wall offset to intersection world coords
                intersect_x = seg.start_vertex[0] + wall_dir[0] * wall_offset_along
                intersect_y = seg.start_vertex[1] + wall_dir[1] * wall_offset_along
                # Raw distance from player to intersection
                hit_dist = math.hypot(intersect_x - player_x, intersect_y - player_y)

                inv_scale = 1.0 / rw_scale1


            if b_draw_upper_wall:
                draw_upper_wall_y1 = wall_y1 - 1
                draw_upper_wall_y2 = portal_y1
                if b_draw_ceil:
                    cy1 = upper_clip[x] + 1
                    cy2 = int(min(draw_wall_y1 - 1, lower_clip[x] - 1))
                    renderer.draw_flat(tex_ceil_id, light_level, x, cy1, cy2, world_front_z1)
                
                wy1 = int(max(draw_upper_wall_y1, upper_clip[x] + 1))
                wy2 = int(min(draw_upper_wall_y2, lower_clip[x] - 1))
                # clamp to screen
                wy1 = max(0, min(wy1, HEIGHT))
                wy2 = max(0, min(wy2, HEIGHT))
                # check that wy2 is bigger than wy1
                if wy1 < wy2:
                    # update wall_depth buffer
                    renderer.z_buffer[x, wy1:wy2] = hit_dist
                    # draw the column
                    renderer.draw_wall_col(
                        framebuffer, upper_wall_texture, wall_offset_along, x, wy1, wy2,
                        upper_tex_alt, inv_scale, light_level,
                    )
                
                if upper_clip[x] < wy2:
                    upper_clip[x] = wy2
                
                portal_y1 += portal_y1_step
            if b_draw_ceil:
                cy1 = upper_clip[x] + 1
                cy2 = int(min(draw_wall_y1 - 1, lower_clip[x] - 1))
                renderer.draw_flat(tex_ceil_id, light_level, x, cy1, cy2, world_front_z1)
                
                
                if upper_clip[x] < cy2:
                    upper_clip[x] = cy2

            if b_draw_lower_wall:
                
                if b_draw_floor:
                    fy1 = int(max(draw_wall_y2 + 1, upper_clip[x] + 1))
                    fy2 = lower_clip[x] - 1
                    renderer.draw_flat(tex_floor_id, light_level, x, fy1, fy2, world_front_z2)
                
                draw_lower_wall_y1 = portal_y2 - 1
                draw_lower_wall_y2 = wall_y2
                
                wy1 = int(max(draw_lower_wall_y1, upper_clip[x] + 1))
                wy2 = int(min(draw_lower_wall_y2, lower_clip[x] - 1))
                # clamp to screen height
                wy1 = max(0, min(wy1, HEIGHT))
                wy2 = max(0, min(wy2, HEIGHT))
                # check that wy2 is bigger than wy1
                if wy1 < wy2:                    
                    # update z buffer
                    renderer.z_buffer[x, wy1:wy2] = hit_dist
                    # draw the wall column
                    renderer.draw_wall_col(
                        framebuffer, lower_wall_texture, wall_offset_along, x, wy1, wy2,
                        lower_tex_alt, inv_scale, light_level,
                    )
                if lower_clip[x] > wy1:
                    lower_clip[x] = wy1
                portal_y2 += portal_y2_step

            if b_draw_floor:
                fy1 = int(max(draw_wall_y2 + 1, upper_clip[x] + 1))
                fy2 = lower_clip[x] - 1
                renderer.draw_flat(tex_floor_id, light_level, x, fy1, fy2, world_front_z2)
                if lower_clip[x] > draw_wall_y2 + 1:
                    lower_clip[x] = fy1

            rw_scale1 += rw_scale_step
            wall_y1 += wall_y1_step
            wall_y2 += wall_y2_step


    def init_screen_range(self):
        self.screen_range = set(range(WIDTH))

    def clip_solid_walls(self, x_start, x_end):
        if self.screen_range:
            curr_wall = set(range(x_start, x_end))
            if intersection := curr_wall & self.screen_range:
                if len(intersection) == len(curr_wall):
                    self.draw_solid_wall_range(x_start, x_end -1)
                else:
                    arr = sorted(intersection)
                    x, x2 = arr[0], arr[-1]
                    for x1, x2 in zip(arr, arr[1:]):
                        if x2 - x1 > 1:
                            self.draw_solid_wall_range(x, x1)
                            x = x2
                    self.draw_solid_wall_range(x, x2)

                self.screen_range -= intersection
        else:
            self.engine.bsp.is_traverse_bsp = False


    def clip_portal_walls(self, x_start, x_end):
        curr_wall = set(range(x_start, x_end))

        if intersection := curr_wall & self.screen_range:
            if len(intersection) == len(curr_wall):
                self.draw_portal_wall_range(x_start, x_end -1)
            else:
                arr = sorted(intersection)
                x = arr[0]
                for x1, x2 in zip(arr, arr[1:]):
                    if x2 - x1 > 1:
                        self.draw_portal_wall_range(x, x1)
                        x = x2
                self.draw_portal_wall_range(x, arr[-1])

    def classify_segment(self, segment, x1, x2, rw_angle1):
        self.seg = segment
        self.rw_angle1 = rw_angle1

        # does not cross a pixel?
        if x1 == x2: 
            return None
        
        back_sector = segment.back_sector
        front_sector = segment.front_sector

        # handle solid walls
        if back_sector is None:
            self.clip_solid_walls(x1, x2)
            return None
        
        # wall with window 
        if (front_sector.ceil_height != back_sector.ceil_height or
            front_sector.floor_height != back_sector.floor_height):
            self.clip_portal_walls(x1, x2)
            return None
        
        # reject empty lines used for triggers etc
        if (back_sector.ceil_texture == front_sector.ceil_texture and
            back_sector.floor_texture == front_sector.floor_texture and 
            back_sector.light_level == front_sector.light_level and
            self.seg.linedef.front_sidedef.middle_texture == '-'):
            return None
        
        # borders with different light levels or textures
        self.clip_portal_walls(x1, x2)