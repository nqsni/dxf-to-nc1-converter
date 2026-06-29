import ezdxf
import math
import argparse
from pathlib import Path


# ═══════════════════════════════════════════
#  GEOMETRY HELPERS
# ═══════════════════════════════════════════

def polygon_area(pts):
    n = len(pts)
    a = 0.0
    for i in range(n):
        j = (i + 1) % n
        a += pts[i][0] * pts[j][1]
        a -= pts[j][0] * pts[i][1]
    return abs(a) / 2.0


def polygon_perimeter(pts):
    n = len(pts)
    return sum(
        math.sqrt((pts[(i+1)%n][0]-pts[i][0])**2 + (pts[(i+1)%n][1]-pts[i][1])**2)
        for i in range(n)
    )


def ensure_clockwise(pts):
    """Pastikan urutan titik searah jarum jam (CW) sesuai format NC1."""
    n = len(pts)
    signed_area = 0.0
    for i in range(n):
        j = (i + 1) % n
        signed_area += pts[i][0] * pts[j][1]
        signed_area -= pts[j][0] * pts[i][1]
    # signed_area > 0 berarti CCW, balik urutannya jadi CW
    if signed_area > 0:
        return list(reversed(pts))
    return pts


# ═══════════════════════════════════════════
#  DXF PARSER
# ═══════════════════════════════════════════

def parse_dxf(filepath):
    doc = ezdxf.readfile(filepath)
    msp = doc.modelspace()

    polylines = []
    for e in msp:
        if e.dxftype() == 'POLYLINE':
            verts  = list(e.vertices)
            pts    = [(v.dxf.location.x, v.dxf.location.y) for v in verts]
            bulges = [v.dxf.bulge if hasattr(v.dxf, 'bulge') else 0.0 for v in verts]
            polylines.append({'pts': pts, 'bulges': bulges})

    if not polylines:
        raise ValueError("Tidak ada POLYLINE di file DXF!")

    # Outline = POLYLINE dengan vertex terbanyak
    outline_pl  = max(polylines, key=lambda p: len(p['pts']))
    outline_pts = outline_pl['pts']

    # Lubang = POLYLINE dengan tepat 2 vertex dan semua bulge = 1.0
    holes = []
    for p in polylines:
        if p is outline_pl:
            continue
        if len(p['pts']) == 2 and all(abs(b - 1.0) < 0.1 for b in p['bulges']):
            x0, y0  = p['pts'][0]
            x1, y1  = p['pts'][1]
            cx       = (x0 + x1) / 2.0
            cy       = (y0 + y1) / 2.0
            diameter = math.sqrt((x1-x0)**2 + (y1-y0)**2)
            holes.append({'cx': round(cx, 3), 'cy': round(cy, 3),
                          'diameter': round(diameter, 2)})

    return outline_pts, holes


# ═══════════════════════════════════════════
#  NC1 FORMATTER
# ═══════════════════════════════════════════

def fmt_val(v, width=10, decimals=2):
    return f"{v:.{decimals}f}".rjust(width)


def fmt_val3(v, width=10):
    return f"{v:.3f}".rjust(width)


def build_nc1(outline_pts, holes, mark, thickness, grade, qty, drawing_no):
    lines = []

    xs     = [p[0] for p in outline_pts]
    ys     = [p[1] for p in outline_pts]
    length = max(xs) - min(xs)
    width  = max(ys) - min(ys)
    area   = polygon_area(outline_pts)

    weight_per_m2 = thickness * 7.85
    perim_mm      = polygon_perimeter(outline_pts)
    surface_dm2   = (2.0 * area + perim_mm * thickness) / 10000.0

    # ── ST Header ──
    lines.append("ST")
    lines.append(f"** {mark}.nc1")
    lines.append(f"  {drawing_no}")
    lines.append(f"  {drawing_no}")
    lines.append(f"  1")
    lines.append(f"  {mark}")
    lines.append(f"  {grade}")
    lines.append(f"  {qty}")
    lines.append(f"  PL{int(thickness)}")
    lines.append(f"  B")
    lines.append(fmt_val(length,         10, 2))
    lines.append(fmt_val(width,          10, 2))
    lines.append(fmt_val(thickness,      10, 2))
    lines.append(fmt_val(thickness,      10, 2))
    lines.append(fmt_val(thickness,      10, 2))
    lines.append(fmt_val(0.0,            10, 2))
    lines.append(fmt_val3(weight_per_m2, 10))
    lines.append(fmt_val3(surface_dm2,   10))
    lines.append(fmt_val(0.0, 10, 3))
    lines.append(fmt_val(0.0, 10, 3))
    lines.append(fmt_val(0.0, 10, 3))
    lines.append(fmt_val(0.0, 10, 3))
    lines.append("")
    lines.append("")
    lines.append("")

    # ── AK Section ──
    lines.append("")
    lines.append("AK")
    zero5 = "       0.00" * 5
    first = True
    for px, py in outline_pts:
        v1 = f"{px:.2f}".rjust(10)
        v2 = f"{py:.2f}".rjust(10)
        if first:
            lines.append(f"  v{v1}u{v2}{zero5}")
            first = False
        else:
            lines.append(f"  {v1} {v2}{zero5}")
    # tutup kontur kembali ke titik awal
    px0, py0 = outline_pts[0]
    lines.append(f"  {f'{px0:.2f}'.rjust(10)} {f'{py0:.2f}'.rjust(10)}{zero5}")
    lines.append("EN")

    # ── BO Section ──
    if holes:
        lines.append("BO")
        for h in holes:
            xv = f"{h['cx']:.2f}".rjust(10)
            yv = f"{h['cy']:.2f}".rjust(10)
            dv = f"{h['diameter']:.2f}".rjust(10)
            lines.append(f"  v{xv}s{yv}{dv}")
        lines.append("EN")

    return "\n".join(lines) + "\n"


# ═══════════════════════════════════════════
#  MAIN (CLI)
# ═══════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Konversi DXF pelat baja ke NC1")
    parser.add_argument("input")
    parser.add_argument("output", nargs="?")
    parser.add_argument("--thickness", "-t", type=float, required=True)
    parser.add_argument("--grade",     "-g", type=str, default="SS400")
    parser.add_argument("--qty",       "-q", type=int, default=1)
    args = parser.parse_args()

    input_path  = Path(args.input)
    mark        = input_path.stem
    output_path = Path(args.output) if args.output else input_path.with_suffix('.nc1')

    outline_pts, holes = parse_dxf(str(input_path))
    content = build_nc1(
        outline_pts=outline_pts,
        holes=holes,
        mark=mark,
        thickness=args.thickness,
        grade=args.grade,
        qty=args.qty,
        drawing_no=mark,
    )

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Selesai -> {output_path}")
    print(content)


if __name__ == "__main__":
    main()