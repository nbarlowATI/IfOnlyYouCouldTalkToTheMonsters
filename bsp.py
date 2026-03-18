from pygame.math import Vector2 as vec2
from doomsettings import *

class BSP:
    SUB_SECTOR_IDENTIFIER = 0x8000
    def __init__(self, engine):
        self.engine = engine
        self.player = engine.player
        self.nodes = engine.wad_data.nodes
        self.sub_sectors = engine.wad_data.sub_sectors
        self.segments = engine.wad_data.segments
        self.root_node_id = len(self.nodes) -1 
        self.is_traverse_bsp = True

    @staticmethod 
    def norm(angle):
        return angle % 360

    @staticmethod
    def angle_to_x(angle):
        if angle > 0:
            x = SCREEN_DIST - math.tan(math.radians(angle)) * H_WIDTH
        else:
            x = -math.tan(math.radians(angle)) * H_WIDTH + SCREEN_DIST
        return int(x)

    def update(self):
        self.is_traverse_bsp = True
        self.render_bsp_node(node_id=self.root_node_id)
        pass

    def add_segment_to_fov(self, vertex1, vertex2):
        angle1 = self.point_to_angle(vertex1)
        angle2 = self.point_to_angle(vertex2)
        span = self.norm(angle1 - angle2)
        # back face culling
        if span >= 180:
            return False
        rw_angle1 = angle1
        
        angle1 -= self.player.angle
        angle2 -= self.player.angle

        span1 = self.norm(angle1 + H_FOV)
        if span1 > FOV:
            if span1 >= span + FOV:
                return False
            angle1 = H_FOV
        span2 = self.norm(H_FOV - angle2)
        if span2 > FOV:
            if span2 >= span + FOV:
                return False
            angle2 = -H_FOV
        x1 = self.angle_to_x(angle1)
        x2 = self.angle_to_x(angle2)
        return x1, x2, rw_angle1


    def check_bbox(self, bbox):
        a, b = vec2(bbox.left, bbox.bottom), vec2(bbox.left, bbox.top)
        c, d = vec2(bbox.right, bbox.top), vec2(bbox.right, bbox.bottom)

        px, py = self.engine.player.pos
        if px < bbox.left:
            if py > bbox.top:
                bbox_sides = [(b, a), (c, b)]
            elif py < bbox.bottom:
                bbox_sides = [(b,a), (a,d)]
            else:
                bbox_sides = [(b,a)]
        elif px > bbox.right:
            if py > bbox.top:
                bbox_sides = [(c,b), (d,c)]
            elif py < bbox.bottom:
                bbox_sides = [(a, d), (d, c)]
            else:
                bbox_sides = [(d, c)]
        else:
            if py > bbox.top:
                bbox_sides = [(c,b)]
            elif py < bbox.bottom:
                bbox_sides = [(a,d)]
            else:
                return True
        for v1, v2 in bbox_sides:
            angle1 = self.point_to_angle(v1)
            angle2 = self.point_to_angle(v2)
            span = self.norm(angle1-angle2)

            angle1 -= self.player.angle
            span1 = self.norm(angle1 + H_FOV)
            if span1 > FOV:
                if span1 >= span + FOV:
                    continue
            return True
        return False

    def point_to_angle(self, vertex):
        delta = vertex - self.player.pos
        return math.degrees(math.atan2(delta.y, delta.x))

    def render_sub_sector(self, sub_sector_id):
        sub_sector = self.sub_sectors[sub_sector_id]
        for i in range(sub_sector.seg_count):
            seg = self.segments[sub_sector.first_seg_id + i]
            if result:= self.add_segment_to_fov(seg.start_vertex, seg.end_vertex):
                self.engine.seg_handler.classify_segment(seg, *result)
                if self.engine.map_mode:
                    self.engine.map_renderer.draw_seg(seg, sub_sector_id)


    def render_bsp_node(self, node_id):
        if not self.is_traverse_bsp:
            return
        if node_id >= self.SUB_SECTOR_IDENTIFIER:
            sub_sector_id = node_id - self.SUB_SECTOR_IDENTIFIER
            self.render_sub_sector(sub_sector_id)
            return None
        node = self.nodes[node_id]
        is_on_back = self.is_on_back_side(node)
        if is_on_back:
            self.render_bsp_node(node.back_child_id)
            if self.check_bbox(node.bbox['front']):
                self.render_bsp_node(node.front_child_id)
        else:
            self.render_bsp_node(node.front_child_id)
            if self.check_bbox(node.bbox["back"]):
                self.render_bsp_node(node.back_child_id)


    def is_on_back_side(self, node, position=None):
        if not position:
            position = self.player.pos
        dx = position.x - node.x_partition
        dy = position.y - node.y_partition
        return dx * node.dy_partition - dy * node.dx_partition <= 0

    def get_sub_sector_height(self, position=None):
        sub_sector_id = self.root_node_id
        while not sub_sector_id >= self.SUB_SECTOR_IDENTIFIER:
            node = self.nodes[sub_sector_id]

            is_on_back = self.is_on_back_side(node, position)
            if is_on_back:
                sub_sector_id = self.nodes[sub_sector_id].back_child_id
            else:
                sub_sector_id = self.nodes[sub_sector_id].front_child_id

        sub_sector = self.sub_sectors[sub_sector_id - self.SUB_SECTOR_IDENTIFIER]
        seg = self.segments[sub_sector.first_seg_id]
        return seg.front_sector.floor_height
    
    ## collision of player with walls
    def trace_collision(self, start_pos, end_pos, radius=None):
        if radius is None:
            radius = self.player.size
        collisions = self._trace_node(self.root_node_id, end_pos, radius)
        return collisions

    def _trace_node(self, node_id, end_pos, radius):
        if node_id >= self.SUB_SECTOR_IDENTIFIER:
            return self._check_subsector(node_id - self.SUB_SECTOR_IDENTIFIER, end_pos, radius)

        node = self.nodes[node_id]
        side = self.is_on_back_side(node, end_pos)

        front = self._trace_node(node.front_child_id, end_pos, radius)
        back = self._trace_node(node.back_child_id, end_pos, radius)

        return front + back

    def _check_subsector(self, sub_sector_id, end, radius):
        sub_sector = self.sub_sectors[sub_sector_id]
        collisions = []
        for i in range(sub_sector.seg_count):
            seg = self.segments[sub_sector.first_seg_id + i]
#            if seg.back_sector is not None: # portal wall
#                continue
            A = seg.start_vertex
            B = seg.end_vertex
            if circle_segment_collision(end, A, B, radius):
                collisions.append(seg)

        return collisions
    
def circle_segment_collision(P, A, B, radius):
    # Vector from A to B
    AB = B - A
    AP = P - A

    # Project point P onto the segment AB, clamped to the segment
    ab_squared = AB.x**2 + AB.y**2
    if ab_squared == 0:
        # A and B are the same point
        dist_sq = (P - A).length_squared()
        return dist_sq <= radius**2

    # Project AP onto AB to find point D on the segment closest to P
    t = max(0, min(1, (AP.x * AB.x + AP.y * AB.y) / ab_squared))
    D = A + AB * t  # Closest point on the segment to the circle center

    # Distance from player center to closest point on the segment
    dist_squared = (P - D).length_squared()

    return dist_squared <= radius**2
