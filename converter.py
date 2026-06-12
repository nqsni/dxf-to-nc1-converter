import ezdxf
import math
import sys
import argparse
from pathlib import Path


# ═══════════════════════════════════════════
#  GEOMETRY HELPERS
# ═══════════════════════════════════════════

def polygon_area(pts):
    """Luas polygon (Shoelace formula)."""
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


# ═══════════════════════════════════════════
#  DXF PARSER
# ═══════════════════════════════════════════

def parse_dxf(filepath):
    """
    Baca DXF dan kembalikan:
      outline_pts  : list of (x, y) — titik kontur pelat
      holes        : list of {'cx','cy','diameter'}
    """
    doc = ezdxf.readfile(filepath)
    msp = doc.modelspace()

    polylines = []
    for e in msp:
        if e.dxftype() == 'POLYLINE':
            verts = list(e.vertices)
            pts   = [(v.dxf.location.x, v.dxf.location.y) for v in verts]
            bulges = [v.dxf.bulge if hasattr(v.dxf, 'bulge') else 0.0 for v in verts]
            polylines.append({'pts': pts, 'bulges': bulges})

    if not polylines:
        raise ValueError("Tidak ada POLYLINE di file DXF!")

    # ── Outline: POLYLINE dengan semua bulge = 0 dan titik terbanyak ──
    outline_candidates = [p for p in polylines if all(abs(b) < 0.01 for b in p['bulges'])]
    if not outline_candidates:
        raise ValueError("Tidak ada outline pelat (POLYLINE tanpa bulge) ditemukan!")
    # Ambil yang paling banyak vertex (biasanya outline utama)
    outline_pl = max(outline_candidates, key=lambda p: len(p['pts']))
    outline_pts = outline_pl['pts']

    # ── Lubang: POLYLINE dengan bulge ≈ 1.0 (arc) ──
    hole_polylines = [p for p in polylines if any(abs(b - 1.0) < 0.1 for b in p['bulges'])]

    holes = []
    for hp in hole_polylines:
        pts = hp['pts']
        if len(pts) < 2:
            continue
        # 2 vertex: (x, y1) dan (x, y2) dimana y1>y2
        # center = titik tengah, diameter = |y1-y2|
        x0, y0 = pts[0]
        x1, y1 = pts[1]
        cx = (x0 + x1) / 2.0
        cy = (y0 + y1) / 2.0
        # Diameter = jarak antar dua vertex
        diameter = math.sqrt((x1-x0)**2 + (y1-y0)**2)
        holes.append({'cx': round(cx, 3), 'cy': round(cy, 3),
                      'diameter': round(diameter, 2)})

    return outline_pts, holes


# ═══════════════════════════════════════════
#  NC1 FORMATTER
# ═══════════════════════════════════════════

def fmt_val(v, width=10, decimals=2):
    """Format nilai numerik dengan lebar kolom tetap (right-aligned)."""
    s = f"{v:.{decimals}f}"
    return s.rjust(width)


def fmt_val3(v, width=10):
    """Format 3 desimal."""
    return f"{v:.3f}".rjust(width)


def build_nc1(outline_pts, holes, mark, thickness, grade, project, qty, drawing_no):
    """
    Bangun string NC1 (DSTV) lengkap sesuai format asli.
    """
    lines = []

    # ── Hitung dimensi ──
    xs = [p[0] for p in outline_pts]
    ys = [p[1] for p in outline_pts]
    length = max(xs) - min(xs)   # panjang (sumbu X)
    width  = max(ys) - min(ys)   # lebar  (sumbu Y)
    area   = polygon_area(outline_pts)  # mm²

    # ── Berat & area ──
    # weight_per_m2 (kg/m²) = thickness × 7.85
    weight_per_m2 = thickness * 7.85
    # painting field — pakai surface area semua sisi (dm²) ≈ nilai di contoh
    # surface = 2*face + perimeter*thickness (mm²) → dm²
    perim_mm = polygon_perimeter(outline_pts)
    surface_dm2 = (2.0 * area + perim_mm * thickness) / 10000.0

    # ── ST Header ──
    lines.append("ST")
    lines.append(f"** {mark}.nc1")
    lines.append(f"  {project}")
    lines.append(f"  {drawing_no}")
    lines.append(f"  1")
    lines.append(f"  {mark}")
    lines.append(f"  {grade}")
    lines.append(f"  {qty}")
    lines.append(f"  PL{int(thickness)}")
    lines.append(f"  B")

    # Dimensi (right-justified, 10 chars, 2 desimal)
    lines.append(fmt_val(length,    10, 2))
    lines.append(fmt_val(width,     10, 2))
    lines.append(fmt_val(thickness, 10, 2))
    lines.append(fmt_val(thickness, 10, 2))
    lines.append(fmt_val(thickness, 10, 2))
    lines.append(fmt_val(0.0,       10, 2))
    lines.append(fmt_val3(weight_per_m2, 10))
    lines.append(fmt_val3(surface_dm2,   10))
    lines.append(fmt_val(0.0, 10, 3))
    lines.append(fmt_val(0.0, 10, 3))
    lines.append(fmt_val(0.0, 10, 3))
    lines.append(fmt_val(0.0, 10, 3))
    lines.append("")
    lines.append("")
    lines.append("")

    # ── AK Section (kontur) ──
    lines.append("")
    lines.append("AK")

    # Titik kontur dimulai dari (0,0) dan diakhiri kembali ke (0,0)
    # Format baris pertama: "  v       X.XXu      Y.YY       0.00 ..."
    # Format baris berikutnya: "        X.XX       Y.YY       0.00 ..."
    zero7 = "       0.00" * 5  # 5 kolom nol
    first = True
    for px, py in outline_pts:
        v1 = f"{px:.2f}".rjust(10)
        v2 = f"{py:.2f}".rjust(10)
        if first:
            lines.append(f"  v{v1}u{v2}{zero7}")
            first = False
        else:
            lines.append(f"  {v1} {v2}{zero7}")
    # Tutup kontur kembali ke titik awal
    px0, py0 = outline_pts[0]
    v1 = f"{px0:.2f}".rjust(10)
    v2 = f"{py0:.2f}".rjust(10)
    lines.append(f"  {v1} {v2}{zero7}")

    # ── BO Section (lubang) — hanya jika ada lubang ──
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
#  MAIN
# ═══════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Konversi DXF pelat baja → NC1 (DSTV)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument("input",       help="File input .dxf")
    parser.add_argument("output",      nargs="?", help="File output .nc1 (default: nama sama)")
    parser.add_argument("--thickness", "-t", type=float, required=True,
                        help="Ketebalan pelat mm, contoh: 16")
    parser.add_argument("--grade",     "-g", type=str, default="SS400",
                        help="Grade baja (default: SS400)")
    parser.add_argument("--project",   "-p", type=str, default="",
                        help="Kode proyek (baris ke-3 NC1)")
    parser.add_argument("--mark",      "-m", type=str, default=None,
                        help="Mark pelat (default: nama file tanpa ekstensi)")
    parser.add_argument("--drawing",   "-d", type=str, default=None,
                        help="Nomor drawing (default: sama dengan mark)")
    parser.add_argument("--qty",       "-q", type=int, default=2,
                        help="Jumlah pelat (default: 2)")
    args = parser.parse_args()

    input_path  = Path(args.input)
    mark        = args.mark    or input_path.stem
    drawing_no  = args.drawing or mark
    output_path = Path(args.output) if args.output else input_path.with_suffix('.nc1')

    print(f"\n[1/3] Membaca DXF: {input_path}")
    outline_pts, holes = parse_dxf(str(input_path))
    xs = [p[0] for p in outline_pts]; ys = [p[1] for p in outline_pts]
    print(f"      Outline : {len(outline_pts)} titik, "
          f"bbox {max(xs)-min(xs):.2f} × {max(ys)-min(ys):.2f} mm")
    print(f"      Lubang  : {len(holes)} buah")
    if holes:
        for h in holes:
            print(f"        → ({h['cx']}, {h['cy']}) ø{h['diameter']}")

    print(f"\n[2/3] Generate NC1...")
    content = build_nc1(
        outline_pts = outline_pts,
        holes       = holes,
        mark        = mark,
        thickness   = args.thickness,
        grade       = args.grade,
        project     = args.project,
        qty         = args.qty,
        drawing_no  = drawing_no,
    )

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"\n[3/3] SELESAI → {output_path}")
    print(f"\n{'─'*55}")
    print("HASIL NC1:")
    print('─'*55)
    print(content)
    print('─'*55)


if __name__ == "__main__":
    main()
