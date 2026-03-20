npc_types = [
    {
        "type_id": 3004, 
        "species": "ZombieMan",
        "friendliness": 40,
        "original_home": "Earth",
        "goal": "escape",
        "friends": ["ShotgunGuy"],
        "enemies": ["Imp", "Cacodemon"]
    },
    {
        "type_id": 9, 
        "species": "ShotgunGuy",
        "friendliness": 30,
        "original_home": "Earth",
        "goal": "escape",
        "friends": ["ShotgunGuy"],
        "enemies": ["Imp", "Cacodemon"]
    },
    {
        "type_id": 3001, 
        "species": "Imp",
        "friendliness": 0,
        "original_home": "Earth",
        "goal": "burning",
        "friends": ["Cacodemon"],
        "enemies": ["ZombieMan"]
    },
]

names = {
            3004: ["Roger", "Hal", "Owen", "Magnus", "Bill"],
            9: ["Geoff", "Robert", "Luigi", "Johannes"],
            3001: ["Edward", "Tim", "Howard", "Mike"]
        }