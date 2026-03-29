from sounds import SoundEffect
from doomsettings import DOOR_OPEN_SPEED, SOUNDS

class Door:
    def __init__(self, segment, engine):
        self.engine = engine
        self.segment = segment
        self.id = segment.linedef_id
        self.is_opening = False
        self.is_closing = False
        self.is_open = False
        self.is_closed = True
        self.sound_effect = SoundEffect(SOUNDS["door_open"], self.engine)
        # Always raise the sector with the lower ceiling (the door sector),
        # regardless of which side was activated from.
        fs, bs = segment.front_sector, segment.back_sector
        if fs.ceil_height < bs.ceil_height:
            self.door_sector = fs
            self.target_height = bs.ceil_height
        else:
            self.door_sector = bs
            self.target_height = fs.ceil_height
        # Seal the door sector so there is no visible gap when closed
        self.door_sector.ceil_height = self.door_sector.floor_height
        self.open_speed = DOOR_OPEN_SPEED
        

    def toggle_open(self):
        if self.is_open:
            self.is_closing = True
        else:
            self.is_opening = True
            self.engine.doors
        self.sound_effect.play()


    def update(self):
        if self.is_opening:
            if self.door_sector.ceil_height >= self.target_height:
                print("DOOR OPEN!")
                self.door_sector.ceil_height = self.target_height
                self.is_opening = False
                self.is_open = True
                self.is_closed = False
            else:
                self.door_sector.ceil_height = min(
                    self.target_height,
                    self.door_sector.ceil_height + self.open_speed
                )
        if self.is_open:
            self.segment.linedef.front_sidedef.middle_texture = None
            self.is_opening = False
