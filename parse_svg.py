import xml.etree.ElementTree as ET
import svg.path

FILE = 'borders.svg'
SIZE = 427, 136

def convert_point(point, width, height):
    x = int(point.real / width * SIZE[0])
    y = int(point.imag / height * SIZE[1])
    return x+1, y

trans_table = str.maketrans('[]()', '{}{}')

points = {}
ordered_points = []
segments = []

def convert_path(path, width, height):
    for seg in svg.path.parse_path(path):
        if isinstance(seg, svg.path.Line):
            start = convert_point(seg.start, width, height)
            end = convert_point(seg.end, width, height)
            if start not in points:
                points[start] = len(points) + 1
                ordered_points.append(start)
            if end not in points:
                points[end] = len(points) + 1
                ordered_points.append(end)
            segments.append((points[start], points[end]))

def main():
    tree = ET.parse(FILE)
    root = tree.getroot()
    width, height = [float(x) for x in root.get('viewBox').split(' ')][2:]
    for node in root.findall('.//{http://www.w3.org/2000/svg}path'):
        convert_path(node.get('d'), width, height)

    points_string = repr(ordered_points).translate(trans_table)
    segments_string = repr(segments).translate(trans_table)
    print('POINTS='+points_string)
    print('LINES='+segments_string)
    print(max(x[1] for x in ordered_points))

if __name__ == '__main__':
    main()
