#!/usr/bin/python3

import PIL.ImageShow
import PIL.Image
import PIL.ImageColor
import PIL.ImageFilter
import sys
import math
import struct
import itertools

DIAMETER = 136
DIAMETER = int(136*1.8)
COLORS = '''#000000
#0d0a31
#29390e
#41501a
#695c38
#57636c
#606a31
#8e8d87
#8394a4
#a89060
#aca9a2
#cec8be
#f6d89d
#756fcc
#000010
#101010'''.split('\n')


# 18 / 136 pixels can be compressed twice as much
# probably not worthy of extra logic
half_strip = int(DIAMETER / 2 * (1.0 - math.sqrt(1.0 - 0.5**2)))


def compute_palette(input_colors):
    palette = []
    for color in input_colors:
        palette.extend(PIL.ImageColor.getrgb(color))
    palette += [0] * (768-len(palette))
    return palette


def map_to_cylinder(source, output_size):
    width, height = source.size
    out_width, out_height = output_size
    quads = []
    prev_y = 0
    for y in range(out_height):
        bbox = (0, y, out_width, y+1)
        new_y = math.asin((y+1)/out_height*2 - 1) / math.pi * height + height/2
        quad = (
            0, prev_y,
            0, new_y,
            width, new_y,
            width, prev_y
        )
        quads.append((bbox, quad))
        prev_y = new_y

    return source.transform(
        output_size, PIL.Image.MESH, quads, PIL.Image.BICUBIC)


def convert_colors(source, colors):
    # convert image to fixed palette (no dithering)
    # https://stackoverflow.com/questions/29433243/convert-image-to-specific-palette-using-pil-without-dithering
    image_with_palette = PIL.Image.new(size=(1, 1), mode='P')
    image_with_palette.putpalette(compute_palette(colors))
    target_im = source.im.convert("P", 0, image_with_palette.im)
    return source._new(target_im)


def compress_rows(source):
    w, h = source.size
    data = source.load()
    row_data = []
    for y in range(h):
        for key, groups in itertools.groupby(data[x, y] for x in range(w)):
            c = len(list(groups))
            while c > 0:
                if c > 16:
                    row_data.append((key, 15))
                    c -= 16
                else:
                    row_data.append((key, c - 1))
                    c = 0
    print('original size', w * h)
    print('compressed size', len(row_data))
    return row_data


PALETTE_TYPE = 12
MAP_TYPE = 4


def write_cartridge(filename, data, colors):
    with open('temp.tic', 'wb') as fout:
        for ch_type, chunk_bytes, payload in read_cartridge(filename):
            if ch_type not in (PALETTE_TYPE, MAP_TYPE):
                fout.write(chunk_bytes)
                fout.write(payload)
        write_palette(fout, colors)
        write_rows(fout, data)


def write_palette(fout, colors):
    fout.write(struct.pack('I', 48 << 8 | PALETTE_TYPE))
    fout.write(bytes(compute_palette(COLORS)[:48]))


def write_rows(fout, rows):
    size = (1 +  # DIAMETER size
            len(rows))  # one byte for each tuple in row
    fout.write(struct.pack('I', size << 8 | MAP_TYPE))

    fout.write(struct.pack('H', DIAMETER))
    for color, count in rows:
        fout.write(bytes([count << 4 | color]))


def read_cartridge(filename):
    with open(filename, 'rb') as fin:
        chunk_bytes = fin.read(4)
        while chunk_bytes:
            chunk = struct.unpack('I', chunk_bytes)[0]
            # 5b -> type
            ch_type = chunk & 0b11111
            # 3b -> bank
            # ch_bank = (chunk >> 5) & 0b111
            # 16b -> size
            ch_size = chunk >> 8
            yield ch_type, chunk_bytes, fin.read(ch_size)
            chunk_bytes = fin.read(4)


def main():
    WIDTH = int(DIAMETER * math.pi)
    HEIGHT = DIAMETER

    source = PIL.Image.open(sys.argv[1])
    target = map_to_cylinder(source, (WIDTH, HEIGHT))
    target = target.filter(PIL.ImageFilter.GaussianBlur(1))
    target = convert_colors(target, COLORS)

    target.save('transformed.png')

    data = compress_rows(target)
    write_cartridge(sys.argv[2], data, COLORS)


main()
