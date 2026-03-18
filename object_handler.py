import pygame as pg
from pygame.math import Vector2 as vec2
import clevercsv

from collectible import Collectible, WeaponPickup
from doomsettings import WEAPON_CLASS_MAP
from ornament import Ornament, ExplodingBarrel
from npc import NPC, ZombieMan, ShotgunGuy, Imp

class ObjectHandler:
    def __init__(self, engine):
        self.engine = engine
        self.npcs = []
        self.objects = []
        self.projectiles = []


    def add_objects_npcs(self, difficulty):
        # store pre-computed scaled sprites
        self.sprite_cache = {}
        # read the csv that maps Thing.type to object/npc info
        with open("thing_index.csv", "r") as thingindex:
            dialect = clevercsv.Sniffer().sniff(thingindex.read(), verbose=False)
            thingindex.seek(0)
            reader = clevercsv.reader(thingindex, dialect)
            rows = list(reader)
        # convert into a dict, keyed by thing_type
        columns = rows[0]
        self.thing_index = {}
        for row in rows[1:]:
            thing_type = int(row[0])
            self.thing_index[thing_type] = {}
            for index, value in enumerate(row):
                if index == 0:
                    continue # don't need thing_type again
                self.thing_index[thing_type][columns[index]] = value
        self.parse_things_lump(difficulty)


    def parse_things_lump(self, difficulty):
        """
        Parameters
        ==========
        difficulty: int, where 0 is easy and 2 is hard.  
                    Use with "flags" bit-field to determine which things to instantiate.
        """
        print(f"will look at {len(self.engine.wad_data.things)} things")
        for thing in self.engine.wad_data.things:
            if int(thing.type) not in self.thing_index:
                continue
            flags = thing.flags
            if flags >> difficulty & 1 == 0:
                # not spawned for this difficulty level
                continue
            thing_info = self.thing_index[int(thing.type)]
            if "M" in thing_info["type"]:
                # it is a monster
                self.add_npc(thing, thing_info)
            elif "P" in thing_info["type"]:
                # collectible
                self.add_collectible(thing, thing_info)
            elif "O" in thing_info["type"]:
                # ornament
                self.add_ornament(thing, thing_info)



    def add_npc(self, thing, thing_info):
        if thing_info["class"] == "ZombieMan":
            self.npcs.append(ZombieMan(self.engine, thing.pos, thing.angle))
        elif thing_info["class"] == "ShotgunGuy":
            self.npcs.append(ShotgunGuy(self.engine, thing.pos, thing.angle))
        elif thing_info["class"] == "Imp":
            self.npcs.append(Imp(self.engine, thing.pos, thing.angle))

    def add_collectible(self, thing, thing_info):
        if thing_info["class"] in WEAPON_CLASS_MAP:
            self.objects.append(WeaponPickup(self.engine, thing.pos, thing.angle, thing_info))
        else:
            self.objects.append(Collectible(self.engine, thing.pos, thing.angle, thing_info))

    def add_ornament(self, thing, thing_info):
        if thing_info["class"] == "ExplodingBarrel":
            self.objects.append(ExplodingBarrel(self.engine, thing.pos, thing.angle, thing_info))
        else:
            self.objects.append(Ornament(self.engine, thing.pos, thing.angle, thing_info))


    def update(self):
        for npc in self.npcs:
            npc.update()

        for object in self.objects:
            object.update()

        for projectile in self.projectiles:
            projectile.update()
        self.projectiles = [p for p in self.projectiles if p.exists]


