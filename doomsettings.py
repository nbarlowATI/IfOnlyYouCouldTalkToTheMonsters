from enum import Enum
import math

DOOM_RES = DOOM_W, DOOM_H = 320,200

SCALE = 4.0
WIN_RES = WIDTH, HEIGHT = int(DOOM_W*SCALE), int(DOOM_H*SCALE)

H_WIDTH, H_HEIGHT = WIDTH // 2, HEIGHT // 2

FOV = 90
FOV_RAD = math.pi/2
H_FOV = FOV // 2
H_FOV_RAD = FOV_RAD / 2

PLAYER_SPEED = 0.3
PLAYER_ROT_SPEED = 0.12
PLAYER_HEIGHT = 41
PLAYER_SIZE = 16
PLAYER_CLIMB_SPEED = 0.2
PLAYER_FALL_SPEED = 0.3
PLAYER_STEP_AMPLITUDE = 10
PLAYER_STEP_FREQUENCY = 0.01

# weapon bob
WEAPON_BOB_X_AMPLITUDE = 10
WEAPON_BOB_Y_AMPLITUDE = 10

DOOR_OPEN_SPEED = 1

WEAPON_CHANGE_SPEED = 10

SCREEN_DIST = H_WIDTH / math.tan(math.radians(H_FOV))
COLOUR_KEY = (152, 0, 136)

MOUSE_SENSITIVITY = 0.03
MOUSE_MAX_REL = 40
MOUSE_BORDER_LEFT = 100
MOUSE_BORDER_RIGHT = WIDTH - MOUSE_BORDER_LEFT

# can we pass through a portal wall?
MIN_ROOM_HEIGHT = PLAYER_HEIGHT + 5
MAX_STEP_HEIGHT = 24

# from how far away can we activate a door?
ACTIVATION_DIST = 300

class WALL_TYPE(Enum):
    SOLID_WALL = 0
    DOOR = 1
    PASSABLE = 2
    IMPASSABLE = 3

# for sound effects
SAMPLE_RATE = 11025

# sprites
WEAPON_BUTTONS = {
    '1': "none",
    '2': "chainsaw",
    '3': "pistol",
    '4': "shotgun",
    '5': "chaingun",
}
WEAPON_SPRITES = {
    'none':     'PUNGA0',
    'chainsaw': 'SAWGA0',
    'pistol':   'PISGA0',
    'shotgun':  'SHTGA0',
    'chaingun': 'CHGGA0',
}

WEAPON_DAMAGE = {
    'none':     0,
    'chainsaw': 40,
    'pistol':   20,
    'shotgun':  50,
    'chaingun': 10,
}

WEAPON_RANGE = {
    'none':     500,
    'chainsaw': 80,
    'pistol':   2000,
    'shotgun':  500,
    'chaingun': 2000,
}

WEAPON_PICKUP_RADIUS = 40
HEALTH_PICKUP_RADIUS = 40
ARMOR_PICKUP_RADIUS  = 40
AMMO_PICKUP_RADIUS   = 40

WEAPON_AMMO_TYPE = {
    'none':     None,
    'chainsaw': None,
    'pistol':   'bullets',
    'shotgun':  'shells',
    'chaingun': 'bullets',
}

AMMO_START = {'bullets': 50, 'shells': 0, 'rockets': 0, 'cells': 0}
AMMO_MAX   = {'bullets': 200, 'shells': 50, 'rockets': 50, 'cells': 300}
# Maps thing_info["class"] from thing_index.csv to internal weapon name
WEAPON_CLASS_MAP = {
    'Shotgun':  'shotgun',
    'Chainsaw': 'chainsaw',
    'Chaingun': 'chaingun',
}

MAX_WEAPON_OFFSET = 200

NPC_WALK_SPEED = 0.075           # world units per ms
NPC_PATROL_TURN_INTERVAL = 3000  # ms between random direction changes
NPC_CHASE_RADIUS = 600           # world units; NPC chases player within this range
BARREL_EXPLOSION_RADIUS = 200    # world units
BARREL_EXPLOSION_DAMAGE = 60     # damage at the centre, falls off linearly to zero at radius

ZOMBIE_SHOOT_DAMAGE = 7
ZOMBIE_SHOOT_COOLDOWN = 1500     # ms between shots
ZOMBIE_SHOOT_RANGE = 900
ZOMBIE_SHOOT_PROB = 0.35         # chance to fire each attempt

SHOTGUN_SHOOT_DAMAGE = 15
SHOTGUN_SHOOT_COOLDOWN = 2000
SHOTGUN_SHOOT_RANGE = 650
SHOTGUN_SHOOT_PROB = 0.45

IMP_FIREBALL_SPEED = 0.5      # world units per ms
IMP_FIREBALL_DAMAGE = 8
IMP_FIRE_COOLDOWN = 2500      # ms between shots

SOUNDS = {
    'pistol':         "DSPISTOL",
    'chaingun':       "DSPISTOL",
    'shotgun':        "DSSHOTGN",
    'barrel_explode': "DSBAREXP",
    'door_open':      "DSDOROPN",
    'pain':           "DSPOSACT",
    'death':          "DSPOSDTH",
    'weapon_pickup':  "DSWPNUP",
}

# sprites in the WAD file are larger than world space
# e.g. soldier is 220 pixels vs 56 for canonical doom sprite.
SPRITE_PIX_RATIO = 56 / 220

# sprites can scale up to 2x original image size when 
# player is right next to them.
MAX_SPRITE_HEIGHT_RATIO = 2

# from DOOM Wiki - interpret the bits in the "flags" attribute
# of "Things" in the WAD
WAD_THING_FLAGS = {
    0: "Easy",
    1: "Medium",
    2: "Hard",
    3: "Ambush",
    4: "Not in DM",
    5: "Not in SP",
    6: "Not in Coop"
}

OLLAMA_MODEL = "llama3.2:latest" #"qwen3-v1:8b"
#OLLAMA_MODEL =  'deepseek-r1:8b' #'qwen3-vl:8b'