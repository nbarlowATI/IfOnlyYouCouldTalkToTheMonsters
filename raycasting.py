from pygame.math import Vector2 as vec2
from doomsettings import *
from data_types import Seg
from door import Door

class RayCasting:
    def __init__(self, engine):
        self.engine = engine
        self.player = engine.player
        self.bsp = engine.bsp


    def cast_ray(self, start_pos, direction, distance):
        """
        Traverse the BSP tree, find the first segment intersected by ray.
        """
        def recurse(node_id):
            if node_id >= self.bsp.SUB_SECTOR_IDENTIFIER:
                sub_id = node_id - self.bsp.SUB_SECTOR_IDENTIFIER
                sub = self.bsp.sub_sectors[sub_id]

                closest_hit = None
                closest_t = distance + 1

                for i in range(sub.seg_count):
                    seg = self.bsp.segments[sub.first_seg_id + i]
                    result = self.intersect_ray_segment(start_pos, direction, seg.start_vertex, seg.end_vertex)
                    if result:
                        _, t = result
#                        print(f"got a hit distance {t}")
                        if t < closest_t and t <= distance:
                            closest_hit = seg
                            closest_t = t
                return closest_hit
            node = self.bsp.nodes[node_id]
            # see which side of the segment we are looking at
            side = (start_pos.x - node.x_partition) * node.dy_partition - (start_pos.y - node.y_partition) * node.dx_partition <= 0

            first = node.back_child_id if side else node.front_child_id
            second = node.front_child_id if side else node.back_child_id

            result = recurse(first)
            if result:
                return result
            return recurse(second)
        return recurse(self.bsp.root_node_id)

    def find_activatable_surface(self):
        ray_start = self.player.pos
        angle_rad = math.radians(self.player.angle)
        ray_vector = vec2(math.cos(angle_rad), math.sin(angle_rad))
#        print(f" aboout to cast a ray!")
        hit = self.cast_ray(ray_start, ray_vector, ACTIVATION_DIST)
        if hit:
            if isinstance(hit, Seg) and hit.linedef.line_type == 1:
                if hit.linedef_id not in self.engine.doors:
                    new_door = Door(hit, self.engine)
                    for offset in (-1, 0, 1):
                        self.engine.doors[hit.linedef_id + offset] = new_door
                    print(f"[DOOR REGISTERED] linedef_ids={hit.linedef_id-1},{hit.linedef_id},{hit.linedef_id+1}")
                door = self.engine.doors[hit.linedef_id]
                print(f"[DOOR TOGGLE] linedef_id={hit.linedef_id} "
                      f"is_open={door.is_open} is_opening={door.is_opening}")
            return hit
        return None
        

    def fire_weapon(self):
        pass

    def intersect_ray_segment(self, ray_start, ray_direction, seg_start, seg_end):
        """ 
        All parameters are vec2
        Returns
            hit_position: vec2
            dist: float
        """
        ray_end = ray_start + ray_direction
        ray_dx = ray_end.x - ray_start.x
        ray_dy = ray_end.y - ray_start.y

        seg_dx = seg_end.x - seg_start.x
        seg_dy = seg_end.y - seg_start.y

        denom = ray_dx * seg_dy - ray_dy * seg_dx
        if denom == 0: # parallel lines:
            return None
        
        t1 = ((seg_start.x - ray_start.x) * seg_dy - (seg_start.y - ray_start.y) * seg_dx) / denom
        t2 = ((seg_start.x - ray_start.x) * ray_dy - (seg_start.y - ray_start.y) * ray_dx) / denom
        if t1 >= 0 and 0 <= t2 <= 1:
            hit_x = ray_start.x + ray_dx * t1
            hit_y = ray_start.y + ray_dy * t1
#            print(f"Got a hit {t1} {t2}")
            return vec2(hit_x, hit_y), t1
        return None

    def cast_shot(self, start_pos, direction, max_distance):
        """
        Ray cast that looks for intersections with sprites, if in 
        front of the nearest wall.
        """

        # normalise direction
        dir_len = math.hypot(direction.x, direction.y)
        ray_dir = direction / dir_len

        wall_seg = self.cast_ray(start_pos, direction, max_distance)
        wall_dist = None
