from thing import Thing
from doomsettings import WEAPON_CLASS_MAP, WEAPON_PICKUP_RADIUS, HEALTH_PICKUP_RADIUS, ARMOR_PICKUP_RADIUS, AMMO_PICKUP_RADIUS


class Collectible(Thing):
    def __init__(self, engine, pos, angle, thing_info):
        super().__init__(engine, pos, angle)
        self.sprite_name_base = thing_info["sprite_base"]
        self.world_height = float(thing_info["height"])
        self.radius = float(thing_info["radius"])
        self.pre_cache(self.sprite_name_base)
        self.extra_y_offset = 0

    def update(self):
        super().update()


class HealthBonus(Collectible):
    HEALTH_AMOUNT = 1

    def update(self):
        if not self.exists:
            return
        super().update()
        if (self.engine.player.pos - self.pos).magnitude() < HEALTH_PICKUP_RADIUS:
            self.engine.player.pick_up_health(self.HEALTH_AMOUNT)
            self.exists = False
            self.engine.object_handler.objects.remove(self)


class ArmorPickup(Collectible):
    ARMOR_AMOUNT = 0

    def update(self):
        if not self.exists:
            return
        super().update()
        if (self.engine.player.pos - self.pos).magnitude() < ARMOR_PICKUP_RADIUS:
            self.engine.player.pick_up_armor(self.ARMOR_AMOUNT)
            self.exists = False
            self.engine.object_handler.objects.remove(self)


class ArmorBonus(ArmorPickup):
    ARMOR_AMOUNT = 1


class GreenArmor(ArmorPickup):
    ARMOR_AMOUNT = 100


class BlueArmor(ArmorPickup):
    ARMOR_AMOUNT = 200


class AmmoPickup(Collectible):
    AMMO_TYPE = None
    AMMO_AMOUNT = 0

    def update(self):
        if not self.exists:
            return
        super().update()
        if (self.engine.player.pos - self.pos).magnitude() < AMMO_PICKUP_RADIUS:
            self.engine.player.pick_up_ammo(self.AMMO_TYPE, self.AMMO_AMOUNT)
            self.exists = False
            self.engine.object_handler.objects.remove(self)


class Clip(AmmoPickup):
    AMMO_TYPE = 'bullets'
    AMMO_AMOUNT = 10

class BoxOfBullets(AmmoPickup):
    AMMO_TYPE = 'bullets'
    AMMO_AMOUNT = 50

class ShotgunShells(AmmoPickup):
    AMMO_TYPE = 'shells'
    AMMO_AMOUNT = 4

class BoxOfShotgunShells(AmmoPickup):
    AMMO_TYPE = 'shells'
    AMMO_AMOUNT = 20

class Rocket(AmmoPickup):
    AMMO_TYPE = 'rockets'
    AMMO_AMOUNT = 1

class BoxOfRockets(AmmoPickup):
    AMMO_TYPE = 'rockets'
    AMMO_AMOUNT = 5

class EnergyCell(AmmoPickup):
    AMMO_TYPE = 'cells'
    AMMO_AMOUNT = 40

class EnergyCellPack(AmmoPickup):
    AMMO_TYPE = 'cells'
    AMMO_AMOUNT = 100


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

