#!/usr/bin/env python3
"""Curved MDF corner bracket generator - Python version of curved_bracket_app.html.

Makes, for one set of sizes:
  * the printed bracket STL (through OpenSCAD and curved_bracket.scad),
  * a VCarve-ready DXF per 4x8 sheet (layers: profile, lid rabbet pocket, pilot drills, labels),
  * a cut list and print summary.

Needs: python3, ezdxf (pip install ezdxf), and OpenSCAD on the PATH for the STL.
Written for Vincent Strader's shop. MIT licence.

Examples
  python3 curved_parts.py                                  # the app's defaults: 48 x 16 x 36 in, 3/4" MDF, R75
  python3 curved_parts.py --layout box --L 24 --D 24 --H 30 --T 0.5 --s 0.125 --R 50 --lid
  python3 curved_parts.py --units mm --L 900 --D 400 --H 720 --T 16 --s 3 --R 75 --N 3 --out my_job
Lengths are in --units (in by default); R and the bracket-shape options are always mm.
"""
import argparse, math, os, shutil, subprocess, sys

IN = 25.4


def frac16(mm):
    v = round(mm / IN * 16)
    whole, rem = divmod(v, 16)
    if rem == 0:
        return f'{whole}"'
    g = math.gcd(rem, 16)
    f = f'{rem // g}/{16 // g}'
    return f'{whole} {f}"' if whole else f'{f}"'


def thick_label(mm):
    if abs(mm - 16) < 0.05:
        return '16MM'
    for v, t in [(3.175, '1/8"'), (6.35, '1/4"'), (9.525, '3/8"'), (12.7, '1/2"'), (15.875, '5/8"'), (19.05, '3/4"'), (25.4, '1"')]:
        if abs(mm - v) < 0.05:
            return t
    return f'{mm:g}MM'


# ---------------- layout ----------------
def derive(p):
    L, D, H, R, T = p['L'], p['D'], p['H'], p['R'], p['T']
    C = {'FL': (0, 0, 0, 'front-left'), 'FR': (L, 0, 90, 'front-right'), 'BR': (L, D, 180, 'back-right'), 'BL': (0, D, 270, 'back-left')}
    if p['layout'] == 'L':
        corners, walls = ['FL'], dict(F=1, Lt=1, Rt=0, B=0)
    elif p['layout'] == 'box':
        corners, walls = ['FL', 'FR', 'BR', 'BL'], dict(F=1, Lt=1, Rt=1, B=1)
    else:
        corners, walls = ['FL', 'FR'], dict(F=1, Lt=1, Rt=1, B=0)
    has = lambda c: c in corners
    panels, warn = [], []

    def add(key, name, a0, a1, cs, ce):
        ln = a1 - a0
        panels.append(dict(key=key, name=name, length=ln, cs=cs, ce=ce))
        need = (p['Lf'] if cs else 0) + (p['Lf'] if ce else 0) + 10
        if ln < need:
            warn.append(f'{name} is only {ln:.0f} mm long; the flanges need {need:.0f} mm.')
    if walls['F']:
        add('F', 'Front panel', R if has('FL') else 0, L - R if has('FR') else L, has('FL'), has('FR'))
    if walls['B']:
        add('B', 'Back panel', R if has('BL') else 0, L - R if has('BR') else L, has('BR'), has('BL'))
    if walls['Lt']:
        add('Lt', 'Left side panel', R if has('FL') else 0, D - R if has('BL') else D, has('FL'), has('BL'))
    if walls['Rt']:
        add('Rt', 'Right side panel', R if has('FR') else 0, D - R if has('BR') else D, has('FR'), has('BR'))
    if p['s'] >= T:
        warn.append('The skin has to be thinner than the panels.')
    if R - p['s'] - p['w'] < 6:
        warn.append('Radius too tight for the band under the skin.')
    top = H - p['rd'] - 0.6 if p['lid'] else H - p['margin']
    span = top - p['margin'] - p['bw']
    N = p['N']
    if span < 0 or (N > 1 and span / (N - 1) < p['bw'] + 2):
        warn.append(f'{N} brackets do not fit in the height.')
    zb = [p['margin'] if N == 1 else p['margin'] + span * i / (N - 1) for i in range(N)]
    arc_mid = math.pi / 2 * (R - p['s'] / 2)
    return dict(corners=[(c,) + C[c] for c in corners], walls=walls, panels=panels, zb=zb, arc_mid=arc_mid, warn=warn, has=has)


def round_rect(x0, y0, x1, y1, r):
    """Closed outline as (x, y, bulge) vertices, CCW. r = dict BL/BR/TR/TL radii."""
    B = math.tan(math.pi / 8)
    BL, BR, TR, TL = (r.get(k, 0) for k in ('BL', 'BR', 'TR', 'TL'))
    v = []

    def a(x, y, b=0):
        if v and abs(v[-1][0] - x) < 1e-6 and abs(v[-1][1] - y) < 1e-6:
            v[-1] = (x, y, b or v[-1][2]); return
        v.append((x, y, b))
    a(x0 + BL, y0); a(x1 - BR, y0, B if BR else 0)
    if BR: a(x1, y0 + BR)
    a(x1, y1 - TR, B if TR else 0)
    if TR: a(x1 - TR, y1)
    a(x0 + TL, y1, B if TL else 0)
    if TL: a(x0, y1 - TL)
    a(x0, y0 + BL, B if BL else 0)
    if abs(v[0][0] - v[-1][0]) < 1e-6 and abs(v[0][1] - v[-1][1]) < 1e-6:
        v[0] = (v[0][0], v[0][1], v[-1][2] or v[0][2]); v.pop()
    return v


def lid_shapes(p, dv):
    """Lid outline and plug outline, drawn as seen from below (mirrored left-right), like the app."""
    L, D, R, T, c, ov = p['L'], p['D'], p['R'], p['T'], p['c'], p['ov']
    W, has = dv['walls'], dv['has']
    wl, wr = W['Rt'], W['Lt']                       # mirrored
    cBL, cBR, cTR, cTL = has('FR'), has('FL'), has('BL'), has('BR')
    o = dict(F=ov if W['F'] else 0, B=ov if W['B'] else 0, l=ov if wl else 0, r=ov if wr else 0)
    rr = lambda on: R + ov if on else 0
    outer = round_rect(-o['l'], -o['F'], L + o['r'], D + o['B'], dict(BL=rr(cBL), BR=rr(cBR), TR=rr(cTR), TL=rr(cTL)))
    i = T + c
    ii = dict(F=i if W['F'] else 0, B=i if W['B'] else 0, l=i if wl else 0, r=i if wr else 0)
    pr = max(0, R - i)
    pp = lambda on: pr if on else 0
    plug = round_rect(ii['l'], ii['F'], L - ii['r'], D - ii['B'], dict(BL=pp(cBL), BR=pp(cBR), TR=pp(cTR), TL=pp(cTL)))
    x0, y0 = -o['l'], -o['F']
    sh = lambda v: [(x - x0, y - y0, b) for x, y, b in v]
    return sh(outer), sh(plug), L + o['l'] + o['r'], D + o['F'] + o['B']


def parts_for(p, dv):
    parts = []
    pilot_d, pilot_depth = 2.5, max(4, min(10, p['T'] - 4))
    for pn in dv['panels']:
        ln, H = pn['length'], p['H']
        drills = []
        for z in (dv['zb'] if p['tf'] + p['T'] - 3 >= 9.5 else []):   # panels too thin to screw into get glued, no pilots
            y = z + p['bw'] / 2
            if pn['cs']: drills += [(f * p['Lf'], y) for f in (0.35, 0.75)]
            if pn['ce']: drills += [(ln - f * p['Lf'], y) for f in (0.35, 0.75)]
        parts.append(dict(name=pn['name'], mat='board', t=p['T'], w=ln, h=H, outline=round_rect(0, 0, ln, H, {}), drills=drills,
                          pocket=None, labels=[pn['name'].upper(), f'{fmt(ln, p)} x {fmt(H, p)}', 'INSIDE FACE UP']))
    for c in dv['corners']:
        w = dv['arc_mid']
        parts.append(dict(name=f'Curved skin ({c[4]})', mat='skin', t=p['s'], w=w, h=p['H'], outline=round_rect(0, 0, w, p['H'], {}), drills=[],
                          pocket=None, labels=[f'SKIN {c[0]}', f'{fmt(w, p)} x {fmt(p["H"], p)}', 'BENDS ACROSS THIS WIDTH']))
    if p['lid']:
        outer, plug, w, h = lid_shapes(p, dv)
        parts.append(dict(name='Lid', mat='board', t=p['tl'], w=w, h=h, outline=outer, drills=[], pocket=(outer, plug, p['rd']),
                          labels=['LID', f'{fmt(w, p)} x {fmt(h, p)}', 'RABBET FACE UP = UNDERSIDE', 'FLIP SIDE TO SIDE AFTER CUT']))
    return parts, pilot_d, pilot_depth


def fmt(mm, p):
    return f'{mm:.1f}MM' if p['units'] == 'mm' else frac16(mm)


# ---------------- nesting: shelves on a 48 x 96 in sheet, 1/2 in kept clear at the edges ----------------
SHEET_W, SHEET_H, EDGE = 96 * IN, 48 * IN, 0.5 * IN


def nest(parts, gap):
    W, Hh = SHEET_W - 2 * EDGE, SHEET_H - 2 * EDGE
    groups = {}
    for pt in parts:
        groups.setdefault((pt['mat'], round(pt['t'], 2)), []).append(pt)
    sheets, over = [], []
    for key, lst in groups.items():
        lst = sorted(lst, key=lambda q: (-max(q['w'], q['h']), -q['w'] * q['h']))
        mine = []

        def place(sh, pt):
            ors = sorted([(pt['w'], pt['h'], 0), (pt['h'], pt['w'], 90)], key=lambda o: o[1])
            for shf in sh['shelves']:
                for w, h, r in ors:
                    if shf['x'] + w <= W + 1e-6 and h <= shf['h'] + 1e-6:
                        sh['items'].append(dict(pt=pt, x=shf['x'], y=shf['y'], r=r)); shf['x'] += w + gap; return True
            for w, h, r in ors:
                if sh['ny'] + h <= Hh + 1e-6 and w <= W + 1e-6:
                    sh['shelves'].append(dict(y=sh['ny'], h=h, x=w + gap)); sh['items'].append(dict(pt=pt, x=0, y=sh['ny'], r=r)); sh['ny'] += h + gap; return True
            return False
        for pt in lst:
            if not any(place(sh, pt) for sh in mine):
                sh = dict(mat=key[0], t=key[1], shelves=[], items=[], ny=0)
                if place(sh, pt): mine.append(sh)
                else: over.append(pt)
        sheets += mine
    for i, sh in enumerate(sheets):
        sh['index'] = i + 1
        for it in sh['items']:
            it['x'] += EDGE; it['y'] += EDGE
    return sheets, over


def xf(it, x, y):
    return (it['x'] + (it['pt']['h'] - y), it['y'] + x) if it['r'] else (it['x'] + x, it['y'] + y)


def write_dxf(p, sh, fn):
    import ezdxf
    k = 1 / IN if p['units'] == 'in' else 1.0
    dstr = (lambda mm: f'{mm:.1f}'.replace('.', 'p') + 'MM') if p['units'] == 'mm' else (lambda mm: f'{mm / IN:.3f}'.replace('.', 'p') + 'IN')
    doc = ezdxf.new('R2000', setup=True)
    doc.header['$INSUNITS'] = 1 if p['units'] == 'in' else 4
    doc.header['$MEASUREMENT'] = 0 if p['units'] == 'in' else 1
    msp = doc.modelspace()
    ly = dict(sheet=('SHEET_48x96_NOCUT', 8), profile=('PROFILE_THROUGH_CUT', 1), labels=('LABELS_NOCUT', 7))
    for n, col in ly.values():
        doc.layers.add(n, color=col)

    def poly(verts, it, layer):
        pts = []
        for x, y, b in verts:
            X, Y = xf(it, x, y)
            pts.append((X * k, Y * k, b))  # xf is a pure rotation, so arc bulges keep their sign
        msp.add_lwpolyline(pts, format='xyb', close=True, dxfattribs={'layer': layer})
    msp.add_lwpolyline([(0, 0), (SHEET_W * k, 0), (SHEET_W * k, SHEET_H * k), (0, SHEET_H * k)], close=True, dxfattribs={'layer': ly['sheet'][0]})
    for it in sh['items']:
        pt = it['pt']
        poly(pt['outline'], it, ly['profile'][0])
        if pt['pocket']:
            outer, plug, depth = pt['pocket']
            layer = f'POCKET_LID_RABBET_{dstr(depth)}_DEEP'
            if layer not in doc.layers: doc.layers.add(layer, color=5)
            # VCarve pockets the area between the outline and the plug (two nested closed vectors)
            poly(outer, it, layer); poly(plug, it, layer)
        if pt['drills']:
            layer = f'DRILL_PILOT_{dstr(2.5)}_DIA_{dstr(max(4, min(10, p["T"] - 4)))}_DEEP'
            if layer not in doc.layers: doc.layers.add(layer, color=3)
            for x, y in pt['drills']:
                X, Y = xf(it, x, y)
                msp.add_circle((X * k, Y * k), 1.25 * k, dxfattribs={'layer': layer})
        cx, cy = xf(it, pt['w'] / 2, pt['h'] / 2)
        th = min(25, max(8, min(pt['w'], pt['h']) * 0.06))
        for j, s in enumerate(pt['labels']):
            t = msp.add_text(s, height=th * k, dxfattribs={'layer': ly['labels'][0]})
            t.set_placement((cx * k, (cy + (len(pt['labels']) / 2 - j - 0.5) * th * 1.6) * k), align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER)
    doc.saveas(fn)
    return doc


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--units', choices=['in', 'mm'], default='in')
    ap.add_argument('--layout', choices=['L', 'U', 'box'], default='U', help='L = 1 corner, U = 2 front corners, box = 4 corners')
    ap.add_argument('--L', type=float, help='outside length (front)')
    ap.add_argument('--D', type=float, help='outside depth (sides)')
    ap.add_argument('--H', type=float, help='height')
    ap.add_argument('--T', type=float, help='panel thickness')
    ap.add_argument('--s', type=float, help='skin thickness')
    ap.add_argument('--R', type=float, default=75, help='outside curve radius, mm')
    ap.add_argument('--N', type=int, default=4, help='brackets per corner')
    ap.add_argument('--margin', type=float, default=30, help='end bracket in from the edge, mm')
    ap.add_argument('--lid', action='store_true')
    ap.add_argument('--tl', type=float, help='lid thickness (default = panel thickness)')
    ap.add_argument('--c', type=float, default=1.0, help='lid clearance per side, mm')
    ap.add_argument('--rd', type=float, default=6, help='lid plug (rabbet) depth, mm')
    ap.add_argument('--ov', type=float, default=0, help='lid overhang, mm')
    for k, v in dict(bw=22, w=16, Lf=40, tf=5, d=4.2, g=2, bridge=20).items():
        ap.add_argument('--' + k, type=float, default=v, help='bracket shape, mm')
    ap.add_argument('--out', default='curved_job')
    a = ap.parse_args()
    u = IN if a.units == 'in' else 1.0
    p = dict(units=a.units, layout=a.layout, R=a.R, N=a.N, margin=a.margin, lid=a.lid, c=a.c, rd=a.rd, ov=a.ov,
             bw=a.bw, w=a.w, Lf=a.Lf, tf=a.tf, d=a.d, g=a.g, bridge=a.bridge)
    p['L'] = (a.L if a.L is not None else (48 if a.units == 'in' else 1219.2)) * u
    p['D'] = (a.D if a.D is not None else (16 if a.units == 'in' else 406.4)) * u
    p['H'] = (a.H if a.H is not None else (36 if a.units == 'in' else 914.4)) * u
    p['T'] = (a.T if a.T is not None else (0.75 if a.units == 'in' else 19.05)) * u
    p['s'] = (a.s if a.s is not None else (0.25 if a.units == 'in' else 6.35)) * u
    p['tl'] = a.tl * u if a.tl is not None else p['T']
    dv = derive(p)
    for w in dv['warn']:
        print('WARNING:', w)
    os.makedirs(a.out, exist_ok=True)
    parts, pd, pdep = parts_for(p, dv)
    sheets, over = nest(parts, 12.7)
    files = []
    for sh in sheets:
        fn = os.path.join(a.out, f'sheet{sh["index"]}_{thick_label(sh["t"]).replace(chr(34), "in").replace("/", "-")}_{"flexMDF" if sh["mat"] == "skin" else "MDF"}.dxf')
        write_dxf(p, sh, fn); files.append(fn)
    stl = os.path.join(a.out, 'bracket.stl')
    scad = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'curved_bracket.scad')
    if shutil.which('openscad'):
        defs = []
        for k in ('R', 'T', 's', 'bw', 'w', 'Lf', 'tf', 'd', 'g', 'bridge'):
            defs += ['-D', f'{k}={p[k]}']
        subprocess.run(['openscad', '-o', stl] + defs + [scad], check=True, capture_output=True)
        files.append(stl)
    else:
        print('OpenSCAD not found: open curved_bracket.scad in OpenSCAD to export the bracket STL.')
    total = len(dv['corners']) * p['N']
    lines = [f'Layout {p["layout"]}: {fmt(p["L"], p)} x {fmt(p["D"], p)} x {fmt(p["H"], p)} high, R {p["R"]:g} mm', '', 'CNC PARTS']
    for pt in parts:
        lines.append(f'  {pt["name"]}: {fmt(pt["w"], p)} x {fmt(pt["h"], p)}, {thick_label(pt["t"])} {"flexible MDF" if pt["mat"] == "skin" else "MDF"}')
    for pt in over:
        lines.append(f'  DOES NOT FIT A 4 x 8 SHEET: {pt["name"]}')
    lines += ['', f'BRACKETS: {total} ({p["N"]} per corner), bottoms at ' + ', '.join(fmt(z, p) for z in dv['zb']) + ' from the bottom edge']
    open(os.path.join(a.out, 'cut_list.txt'), 'w').write('\n'.join(lines) + '\n')
    files.append(os.path.join(a.out, 'cut_list.txt'))
    print('\n'.join(lines)); print('wrote', *files, sep='\n  ')


if __name__ == '__main__':
    main()
