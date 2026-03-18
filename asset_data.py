import pygame as pg
from doomsettings import *

class Patch:
    def __init__(self, asset_data, name, is_sprite=True):
        self.asset_data = asset_data
        self.name = name
        self.palette = asset_data.palette
        self.patch_index = self.asset_data.get_lump_index(name)
        if not self.patch_index:
            return
        self.header, self.columns = self.load_patch_columns(name)
        self.width = self.header.width
        self.height = self.header.height
        self.image = self.get_image()
        if is_sprite:
            self.image = pg.transform.scale(
                self.image, (
                    self.width * SCALE, self.height * SCALE
                )

            )

    def get_image(self):
        image = pg.Surface([self.width, self.height])
        image.fill(COLOUR_KEY)
        image.set_colorkey(COLOUR_KEY)

        ix = 0
        for column in self.columns:
            if column.top_delta == 0xFF:
                ix += 1
                continue
            for iy in range(column.length):
                colour_idx = column.data[iy]
                colour = self.palette[colour_idx]
                image.set_at([ix, iy+column.top_delta], colour)
        return image

    def load_patch_columns(self, patch_name):
        reader = self.asset_data.reader
        
        patch_offset = reader.directory[self.patch_index]['lump_offset']

        patch_header = self.asset_data.reader.read_patch_header(patch_offset)
        patch_columns = []

        for i in range(patch_header.width):
            offs = patch_offset + patch_header.column_offset[i]
            while True:
                patch_column, offs = reader.read_patch_column(offs)
                patch_columns.append(patch_column)
                if patch_column.top_delta == 0xFF:
                    break
        return patch_header, patch_columns

class Texture:
    def __init__(self, asset_data, tex_map):
        self.asset_data = asset_data
        self.tex_map = tex_map
        self.image = self.get_image()

    def get_image(self):
        image = pg.Surface([self.tex_map.width, self.tex_map.height])
        image.fill(COLOUR_KEY)
        image.set_colorkey(COLOUR_KEY)
        #
        for patch_map in self.tex_map.patch_maps:
            patch = self.asset_data.texture_patches[patch_map.p_name_index]
            image.blit(patch.image, (patch_map.x_offset, patch_map.y_offset))
        image = pg.surfarray.array3d(image)
        
        return image

class Flat:
    def __init__(self, asset_data, flat_data):
        self.flat_data = flat_data
        self.palette = asset_data.palette
        self.image = self.get_image()

    def get_image(self):
        image = pg.Surface([64, 64])
        for i, color_idx in enumerate(self.flat_data):
            ix = i % 64
            iy = i // 64
            color = self.palette[color_idx]
            image.set_at([ix, iy], color)
        image = pg.surfarray.array3d(image)
        return image



class AssetData:
    def __init__(self, wad_data):
        self.wad_data = wad_data
        self.reader = wad_data.reader
        self.get_lump_index = wad_data.get_lump_index

        self.palettes = self.wad_data.get_lump_data(
            reader_func = self.reader.read_palette,
            lump_index = self.get_lump_index("PLAYPAL"),
            num_bytes = 256 * 3
        )
        self.palette_index = 0
        self.palette = self.palettes[self.palette_index]

        self.sprites = self.get_sprites(start_marker="S_START", end_marker="S_END")
        self.status_bar = self.get_status_bar()
        self.doomguy_faces = self.get_doomguy()
        # texture patch names
        self.p_names = self.wad_data.get_lump_data(
            self.reader.read_string,
            self.get_lump_index('PNAMES'),
            num_bytes=8,
            header_length=4
        )

        # texture patches
        self.texture_patches = []
        for p_name in self.p_names:
            patch = Patch(self, p_name, is_sprite=False)
            if patch.patch_index:
                self.texture_patches.append(patch)
        # wall textures
        texture_maps = self.load_texture_maps(texture_lump_name='TEXTURE1')
        if self.get_lump_index('TEXTURE2'):
            texture_maps += self.load_texture_maps(texture_lump_name='TEXTURE2')

        self.textures = {
            tex_map.name: Texture(self, tex_map).image for tex_map in texture_maps
        }
        # flat textures
        self.textures |= self.get_flats()

        # sky
        self.sky_id = 'F_SKY1'
        self.sky_tex_name = 'SKY1'
        self.sky_tex = self.textures[self.sky_tex_name]

    def load_texture_maps(self, texture_lump_name):
        tex_idx = self.get_lump_index(texture_lump_name)
        offset = self.reader.directory[tex_idx]['lump_offset']

        texture_header = self.reader.read_texture_header(offset)

        texture_maps = []
        for i in range(texture_header.texture_count):
            tex_map = self.reader.read_texture_map(
                offset + texture_header.texture_data_offset[i]
            )
            texture_maps.append(tex_map)
        return texture_maps

    def get_sprites(self, start_marker="S_START", end_marker="S_END"):
        idx1 = self.get_lump_index(start_marker) + 1
        idx2 = self.get_lump_index(end_marker)
        lumps_info = self.reader.directory[idx1:idx2]
        sprites = {
            lump['lump_name'] : Patch(self, lump['lump_name']).image for lump in lumps_info
        }
        return sprites
    
    def get_doomguy(self, start_marker="STFST01", end_marker="STFDEAD0"):
        idx1 = self.get_lump_index(start_marker)
        idx2 = self.get_lump_index(end_marker) + 1
        lumps_info = self.reader.directory[idx1:idx2]
        faces = {
            lump["lump_name"] : Patch(self, lump["lump_name"]).image for lump in lumps_info
        }
        return faces

    def get_status_bar(self, name="STBAR"):
        idx = self.get_lump_index(name)
        lump_info = self.reader.directory[idx]
        return Patch(self, lump_info["lump_name"]).image
    
    def get_flats(self, start_marker='F_START', end_marker='F_END'):
        idx1 = self.get_lump_index(start_marker) + 1
        idx2 = self.get_lump_index(end_marker)
        flat_lumps = self.reader.directory[idx1: idx2]

        flats = {}
        for flat_lump in flat_lumps:
            offset = flat_lump['lump_offset']
            size = flat_lump['lump_size']  # 64 x 64

            flat_data = []
            for i in range(size):
                flat_data.append(self.reader.read_1_byte(offset + i, byte_format='B'))

            flat_name = flat_lump['lump_name']
            flats[flat_name] = Flat(self, flat_data).image
        return flats