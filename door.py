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
        self.target_height = self.segment.front_sector.ceil_height
        self.open_speed = DOOR_OPEN_SPEED
        print(f"creating a door!!! {self.id}")
        

    def toggle_open(self):
        if self.is_open:
            self.is_closing = True
        else:
            self.is_opening = True
            self.engine.doors
        self.sound_effect.play()


    def update(self):
        if self.is_opening:
            if self.segment.back_sector.ceil_height == self.target_height:
                print("DOOR OPEN!")
                self.is_opening = False
                self.is_open = True
                self.is_closed = False
            else:
                self.segment.back_sector.ceil_height = min(
                    self.target_height,
                    self.segment.back_sector.ceil_height + self.open_speed
                )
        if self.is_open:
            self.segment.linedef.front_sidedef.middle_texture = None
            self.is_opening = False
