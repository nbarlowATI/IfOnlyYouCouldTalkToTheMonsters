import math
import random
import time
import pygame as pg
from doomsettings import *

class MapRenderer:

    def __init__(self, engine):
        self.engine = engine
        self.wad_data = engine.wad_data
        self.vertexes = self.wad_data.vertexes
        self.linedefs = self.wad_data.linedefs
        self.xmin, self.xmax, self.ymin, self.ymax = self.get_map_bounds()
        self.vertexes = [pg.Vector2(self.remap_x(v.x), self.remap_y(v.y)) for v in self.vertexes]

    def get_map_bounds(self):
        x_sorted = sorted(self.vertexes,key=lambda v: v.x)
        x_min, x_max = x_sorted[0].x, x_sorted[-1].x
        y_sorted = sorted(self.vertexes, key=lambda v: v.y)
        y_min, y_max = y_sorted[0].y, y_sorted[-1].y
        return x_min, x_max, y_min, y_max

    def remap_x(self, n, out_min=30, out_max=WIDTH-30):
        return (max(self.xmin, min(n,self.xmax)) - self.xmin) * (
            out_max - out_min) / (self.xmax - self.xmin ) + out_min

    def remap_y(self, n, out_min=30, out_max=HEIGHT-30):
        return HEIGHT - (max(self.ymin, min(n, self.ymax)) - self.ymin) * (
            out_max - out_min) / (self.ymax - self.ymin) - out_min

    def get_colour(self, seed):
        random.seed = seed
        rnd = random.randrange
        rng = 100, 256
        return rnd(*rng), rnd(*rng), rnd(*rng)

    def draw(self):
        self.draw_vertices()
        self.draw_linedefs()
        self.draw_player_pos()
        self.draw_npcs()
        self.draw_barrels()
        #self.draw_node(node_id=self.engine.bsp.root_node_id)

    def draw_vlines(self, x1, x2, sub_sector_id):
        colour = self.get_colour(sub_sector_id)
        pg.draw.line(self.engine.screen, colour, (x1, 0), (x1, HEIGHT), 3)
        pg.draw.line(self.engine.screen, colour, (x2, 0), (x2, HEIGHT), 3)

    def draw_seg(self, seg, sub_sector_id):
        v1 = self.vertexes[seg.start_vertex_id]
        v2 = self.vertexes[seg.end_vertex_id]
        pg.draw.line(self.engine.screen, 'green', v1, v2, 4)

    def draw_bbox(self, bbox, colour):
        x, y = self.remap_x(bbox.left), self.remap_y(bbox.top)
        w, h = self.remap_x(bbox.right) - x, self.remap_y(bbox.bottom) - y
        pg.draw.rect(self.engine.screen, colour, (x, y, w, h), 2)

    def draw_node(self, node_id):
        node = self.engine.wad_data.nodes[node_id]
        bbox_front = node.bbox["front"]
        bbox_back = node.bbox["back"]
        self.draw_bbox(bbox_front, "green")
        self.draw_bbox(bbox_back, "red")
        x1, y1 = self.remap_x(node.x_partition), self.remap_y(node.y_partition)
        x2 = self.remap_x(node.x_partition + node.dx_partition)
        y2 = self.remap_y(node.y_partition + node.dy_partition)
        pg.draw.line(self.engine.screen, "blue", (x1, y1), (x2, y2), 4)

    def draw_player_pos(self):
        pos = self.engine.player.pos
        x = self.remap_x(pos.x)
        y = self.remap_y(pos.y)
        pg.draw.circle(self.engine.screen, 'orange', (x,y), 8)
        x1 = self.remap_x(pos.x + 500 * math.sin(math.radians(self.engine.player.angle+90)))
        y1 = self.remap_y(pos.y - 500 * math.cos(math.radians(self.engine.player.angle+90)))
        pg.draw.line(self.engine.screen, 'purple', (x,y), (x1,y1), 4)
        self.draw_fov(x,y)

    def draw_fov(self, px, py):
        x, y = self.engine.player.pos
        angle = -self.engine.player.angle +90
        sin_a1 = math.sin(math.radians(angle - H_FOV))
        cos_a1 = math.cos(math.radians(angle - H_FOV))
        sin_a2 = math.sin(math.radians(angle + H_FOV))
        cos_a2 = math.cos(math.radians(angle + H_FOV))
        len_ray = HEIGHT
        x1, y1 = self.remap_x(x + len_ray * sin_a1), self.remap_y(y + len_ray * cos_a1)
        x2, y2 = self.remap_x(x + len_ray * sin_a2), self.remap_y(y + len_ray * cos_a2)
        pg.draw.line(self.engine.screen, "yellow", (px,py), (x1, y1), 4)
        pg.draw.line(self.engine.screen, "yellow", (px,py), (x2, y2), 4)


    def draw_npcs(self):
        for npc in self.engine.object_handler.npcs:
            pos = npc.pos
            x = self.remap_x(pos.x)
            y = self.remap_y(pos.y)
            pg.draw.circle(self.engine.screen, 'blue', (x,y), 8)

    def draw_barrels(self):
        for obj in self.engine.object_handler.objects:
            if obj.sprite_name_base == "BAR1":
                pos = obj.pos
                x = self.remap_x(pos.x)
                y = self.remap_y(pos.y)
                pg.draw.circle(self.engine.screen, 'green', (x,y), 7)



    def draw_linedefs(self):
        for line in self.linedefs:
            p1 = self.vertexes[line.start_vertex_id]
            p2 = self.vertexes[line.end_vertex_id]
            pg.draw.line(self.engine.screen, 'red', p1, p2, 3)

    def draw_vertices(self):
        for v in self.vertexes:
            pg.draw.circle(self.engine.screen, 'white', (v.x, v.y), 4)