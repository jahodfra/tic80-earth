#!/usr/bin/python3

import PIL.ImageShow
import PIL.Image
import PIL.ImageColor
import PIL.ImageFilter
import sys
import math
import struct

DIAMETER = 136

COLORS = [c for c in '''
#000000
#040531
#0d0b37
#15143c

#28294d
#153b06
#fad698
#464766

#3c5316
#2a5a10
#5b5a2b
#725c36

#f7fcac
#8086a2
#000010
#09090a

#a18256
#c9cbd3
#868898
#84915a

#d47b54
#a6a494
#c8a375
#a7aab2

#e5c49d
#f4f5f3
#cfcbc2
#2a350c

#64667f
#596d32
#f6eccd
'''.split('\n') if c]


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


def compress_bits(source):
    w, h = source.size
    data = source.load()
    data = bytes([data[x, y] for y in range(h) for x in range(w)])
    res = []
    for d in data:
        res.append(d & 3)
        res.append(d >> 2 & 3)
        res.append(d >> 4 & 3)
    res.extend([0] * (4 - len(res) % 4))  # make len(res) divisible by 4
    result = []
    for i in range(0, len(res), 4):
        result.append(res[i] | res[i+1] << 2 | res[i+2] << 4 | res[i+3] << 6)
    return result


CHUNK_PALETTE = 12
PALETTE_SIZE = 48
CHUNK_TILES = 1
CHUNK_SPRITES = 2
CHUNK_MAP = 4
WRITE_CHUNKS = (CHUNK_PALETTE, CHUNK_MAP, CHUNK_TILES, CHUNK_SPRITES)


def write_cartridge(filename, data, colors):
    with open('temp.tic', 'wb') as fout:
        for ch_type, chunk_bytes, payload in read_cartridge(filename):
            if ch_type not in WRITE_CHUNKS:
                fout.write(chunk_bytes)
                fout.write(payload)
        write_palette(fout, colors)
        write_rows(fout, data)


def write_palette(fout, colors):
    fout.write(struct.pack('I', 48 << 8 | CHUNK_PALETTE))
    fout.write(bytes(compute_palette(COLORS)[PALETTE_SIZE:2*PALETTE_SIZE]))


def write_rows(fout, rows):
    data_size = len(rows)
    size = (2 +  # height
            2 +  # data size
            PALETTE_SIZE*2)
    part1, part2, part3 = [], [], []
    if len(rows) <= 8192 - size:
        part1 = rows
    else:
        part1, rows = rows[:8192-size], rows[8192-size:]
        if len(rows) <= 8192:
            part2 = rows
        else:
            part2, part3 = rows[:8192], rows[8192:]

    assert len(part3) <= 32640

    size += len(part1)  # compressed data

    print('Tiles size:', size)
    fout.write(struct.pack('I', size << 8 | CHUNK_TILES))

    fout.write(struct.pack('H', DIAMETER))
    fout.write(struct.pack('H', data_size))
    fout.write(bytes(compute_palette(COLORS)[:2*PALETTE_SIZE]))

    fout.write(bytes(part1))
    if part2:
        print('Sprites size:', len(part2))
        fout.write(struct.pack('I', len(part2) << 8 | CHUNK_SPRITES))
        fout.write(bytes(part2))
    if part3:
        print('Map size:', len(part3))
        fout.write(struct.pack('I', len(part3) << 8 | CHUNK_MAP))
        fout.write(bytes(part3))


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
    # target = target.filter(PIL.ImageFilter.GaussianBlur(1))
    target = convert_colors(target, COLORS)

    target.save('transformed.png')

    data = compress_bits(target)
    write_cartridge(sys.argv[2], data, COLORS)


main()
