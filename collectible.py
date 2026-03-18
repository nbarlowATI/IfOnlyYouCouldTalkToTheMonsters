from thing import Thing
from doomsettings import WEAPON_CLASS_MAP, WEAPON_PICKUP_RADIUS


class Collectible(Thing):
    def __init__(self, engine, pos, angle, thing_info):
        super().__init__(engine, pos, angle)
        self.sprite_name_base = thing_info["sprite_base"]
        self.world_height = float(thing_info["height"])
        self.radius = float(thing_info["radius"])
        self.pre_cache(self.sprite_name_base)
        self.extra_y_offset = 20

    def update(self):
        super().update()


class WeaponPickup(Collectible):
    def __init__(self, engine, pos, angle, thing_info):
        super().__init__(engine, pos, angle, thing_info)
        self.weapon_name = WEAPON_CLASS_MAP.get(thing_info["class"])

    def update(self):
        if not self.exists:
            return
        super().update()
        if self.weapon_name:
            dp = self.engine.player.pos - self.pos
            if dp.magnitude() < WEAPON_PICKUP_RADIUS:
                self.engine.player.pick_up_weapon(self.weapon_name)
                self.exists = False
                self.engine.object_handler.objects.remove(self)

