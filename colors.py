from palette import COLORS
import PIL
from PIL import ImageColor
import colorsys

def dist2(color1, color2):
    r1, g1, b1 = color1
    r2, g2, b2 = color2
    return (r2-r1)**2 + (g2-g1)**2 + (b2-b1)**2

def dot(alpha, color):
    return tuple(min(int(alpha * x), 255) for x in color)

darken = []
lighten = []
colors = [PIL.ImageColor.getrgb(color) for color in COLORS]
for c in colors:
    dark = dot(0.3, c)
    light = dot(4, c)
    di = min(range(len(colors)), key=lambda i: dist2(colors[i], dark))
    darken.append(di)
    li = min(range(len(colors)), key=lambda i: dist2(colors[i], light))
    lighten.append(li)
print('[0]='+','.join(str(c) for c in lighten))
