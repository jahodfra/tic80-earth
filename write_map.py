#!/usr/bin/python3

import PIL.ImageShow
import PIL.Image
import PIL.ImageColor
import PIL.ImageFilter
import sys
import math
import struct

DIAMETER = 136

from palette import COLORS

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


def image_to_bytes(source):
    w, h = source.size
    data = source.load()
    return bytes([data[x, y] for y in range(h) for x in range(w)])


def ident(x):
    return x


def meassure_compression(target):
    print('Available space: ', 8192*2+32640)

    for compress_func in (
            ident, encode_6b_words, encode_rle_with_mask, encode_rle_2b_runs,
            encode_lzw, encode_lz77):
        print('{}: {} B'.format(
            compress_func.__name__, len(compress_func(target))))


def encode_rle(data, encode_repeat, max_chain):
    mask = 32
    if len(data) == 0:
        return []

    result = []
    prev = data[0]
    chain_size = 1
    for d in data[1:]:
        assert d < mask
        if d == prev and chain_size <= max_chain:
            chain_size += 1
        elif chain_size == 1:
            result.append(d)
            chain_size = 1
            prev = d
        else:
            result.extend(encode_repeat(d, chain_size))
            chain_size = 1
            prev = d
    if chain_size == 1:
        result.append(prev)
    else:
        result.extend(encode_repeat(prev, chain_size))
    return result


def encode_lz77(data):
    max_window_size = 2**11
    max_chain_size = 2**4
    # top 1b is for marking literal
    # TODO: finish
    window = bytearray()
    chain = bytearray()
    result = []
    stop = 255
    for i, d in enumerate(data + bytes([stop])):
        window = data[max(0, i-max_window_size) : i]
        chain.append(d)
        if d == stop or chain not in window or len(chain) > max_chain_size:
            chain.pop()
            start = window.find(chain)
            size = len(chain)
            if size > 0:
                word = 1 << 31 | start << 6 | size-1
                result.append(word // 256)
                result.append(word % 256)
            result.append(d)
            chain = bytearray()
    return result


def encode_lzw(data):
    lookup = {bytes([i]): i for i in range(32)}
    result = []
    chain = bytes()
    table_size = 256**2
    for d in data:
        next_chain = chain + bytes([d])
        if next_chain not in lookup:
            result.append(lookup[chain] // 256)
            result.append(lookup[chain] % 256)
            if len(lookup) < table_size:
                lookup[next_chain] = len(lookup)
            chain = bytes([d])
        else:
            chain = next_chain
    if chain:
        result.append(lookup[chain])
    return result


def encode_rle_with_mask(data):
    return encode_rle(data, lambda ch, size: [size+32, ch], 255-32)


def encode_rle_2b_runs(data):
    return encode_rle(data, lambda ch, size: [(size-1) << 5 + ch], 4)


def encode_6b_words(data):
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

    data = image_to_bytes(target)
    #meassure_compression(data)

    data = encode_6b_words(data)
    write_cartridge(sys.argv[2], data, COLORS)


main()
