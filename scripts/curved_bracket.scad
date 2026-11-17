// Curved MDF corner bracket - OpenSCAD version of the generator in curved_bracket_app.html
// One bracket, lying flat as it prints (the corner's axis is Z). Works with the OpenSCAD Customizer.
// Written for Vincent Strader's shop. MIT licence.
//
// The bracket is a quarter-ring band that sits just inside the bent skin, with a flat flange at each
// end that screws to the inside face of a panel. The band is split into 3 curved ribs by 2 slots.
// Corner frame: the two panels' outside faces are the lines y = 0 (front) and x = 0 (side);
// the outside of the skin is a quarter circle of radius R centred on (R, R).

/* [Assembly] */
// Outside radius of the curve (face of the skin), mm
R = 75;            // [25:1:200]
// Flat panel thickness, mm (19.05 = 3/4", 12.7 = 1/2", 6.35 = 1/4", 16 = 16 mm)
T = 19.05;
// Curved skin (flexible MDF) thickness, mm (3.175 = 1/8", 6.35 = 1/4", 9.525 = 3/8")
s = 6.35;

/* [Bracket shape] */
// Bracket width along the corner (its printed height), mm
bw = 22;           // [14:0.5:40]
// Width of the curved band, mm
w = 16;            // [10:0.5:30]
// Flange length along the panel, mm
Lf = 40;           // [25:0.5:60]
// Flange thickness, mm
tf = 5;            // [3:0.5:8]
// Screw clearance hole, mm (4.2 for #8 or 4 mm screws)
d = 4.2;
// Slot height between the 3 ribs, mm (0 = solid band)
g = 2;             // [0:0.5:4]
// Longest slot window between posts, mm (print bridge)
bridge = 20;

$fn = 96;
Ro = R - s;
Ri = max(2, Ro - w);
Ytop = T + tf;
aIn = (Ytop >= R - Ri) ? acos(min(1, (R - Ytop) / Ri)) : 0;   // degrees

function P(r, a) = [R - r * sin(a), R - r * cos(a)];
function arc(r, a0, a1, n = 40) = [for (i = [0:n]) P(r, a0 + (a1 - a0) * i / n)];
function mir(q) = [q[1], q[0]];

endA = (aIn > 0) ? [[R, T], [R + Lf, T], [R + Lf, Ytop]]
                 : [[R, T], [R + Lf, T], [R + Lf, Ytop], [R, Ytop]];
endB = [for (i = [len(endA) - 1:-1:0]) mir(endA[i])];
profile = concat(arc(Ro, 90, 0), endA, arc(Ri, aIn, 90 - aIn), endB);

// slot windows between posts
Rm = (Ro + Ri) / 2; post = 4; pa = post / Rm * 180 / PI;
wa0 = aIn + pa * 1.5; A = 90 - 2 * wa0;
nWin = max(1, ceil((A * PI / 180 * Ro + post) / (bridge + post)));
winA = (A - (nWin - 1) * pa) / nWin;
rib = (bw - 2 * g) / 3;

module windows2d() {
  for (i = [0:nWin - 1]) {
    s0 = wa0 + i * (winA + pa); s1 = s0 + winA;
    polygon(concat(arc(Ro + 1, s0, s1, 16), arc(Ri - 1, s1, s0, 16)));
  }
}

// teardrop hole along -Y through flange A, point toward +Z (prints without support), with countersink
module hole_A(hx) {
  r = d / 2;
  dk = min(2 * d, bw - 3, d + 2 * (tf - 1));
  csd = max(0, (dk - d) / 2);
  translate([hx, Ytop + 1, bw / 2]) rotate([90, 0, 0])
    linear_extrude(tf + T + 2)
      polygon(concat([for (i = [0:36]) let(a = 135 + 270 * i / 36) [r * cos(a), r * sin(a)]], [[0, r * sqrt(2)]]));
  if (csd > 0.2)
    translate([hx, Ytop - csd, bw / 2]) rotate([-90, 0, 0]) cylinder(h = csd + 0.01, r1 = r, r2 = dk / 2 + 0.01);
}

module holes_A() { for (hx = [R + 0.35 * Lf, R + 0.75 * Lf]) hole_A(hx); }

difference() {
  linear_extrude(bw) polygon(profile);
  if (g > 0 && rib >= 2 && winA * PI / 180 * Ro >= 3)
    for (z = [rib, 2 * rib + g]) translate([0, 0, z]) linear_extrude(g) windows2d();
  holes_A();
  mirror([1, -1, 0]) holes_A();   // same holes in flange B
}
