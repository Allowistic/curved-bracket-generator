# Curved MDF corner brackets: generator scripts

These scripts make the same parts as `curved_bracket_app.html`, for use without a browser.

- `curved_bracket.scad`: one printed bracket, in OpenSCAD. Open it, change the numbers in the Customizer, then export the STL. It lies flat, the way it prints.
- `curved_parts.py`: the whole job from the command line. It writes one VCarve DXF for each 4 x 8 sheet, the bracket STL (it calls OpenSCAD) and a cut list. It needs `pip install ezdxf`, plus OpenSCAD on the PATH for the STL.

```
python3 curved_parts.py --lid                                   # 48 x 16 x 36 in, 3/4" MDF, 75 mm radius, 2 corners
python3 curved_parts.py --layout box --L 24 --D 24 --H 30 --T 0.5 --s 0.125 --R 50 --N 3 --lid --rd 5
python3 curved_parts.py --layout L --L 30 --D 15 --H 10 --T 0.25 --s 0.125 --R 100 --N 2 --margin 20
python3 curved_parts.py --units mm --L 900 --D 400 --H 720 --T 16 --s 3 --R 75 --out my_job
```

Lengths are in `--units`, which is inches unless you set it. The radius and the bracket-shape options are always in mm. `--layout`: `L` is one corner, `U` is two front corners with an open back, and `box` is four corners.

The app is the main tool. It also makes the 3MF plate for the X1C, SVGs, the 3D view and room view. Its DXFs carry a size label on each part as well.

## How the parts go together

- Each flat panel stops where the curve starts, at the radius back from the outside corner.
- The bracket is a quarter-ring band with a flat flange at each end. The flanges screw to the inside faces of the two panels at the corner. The outside of the band holds the bent skin.
- The skin is a strip of flexible MDF. Its height is the box height, and its width is the arc length through the middle of its thickness. It bends around the band and butts against the ends of the panels. The brief didn't show how the skin is fastened, so glue it to the bands and to the panel ends.
- The lid has a rabbet routed on its underside. That leaves a plug that drops inside the panels, with the clearance you set on each walled side. The plug sits on the top bracket in each corner, because the top bracket is placed exactly at the plug depth. The plug's corners curve around the same centre as the skin, so it can't catch on the step where the skin meets a panel.

## DXF layers (for VCarve)

- `PROFILE_THROUGH_CUT`: part outlines. Cut them on the outside.
- `POCKET_LID_RABBET_<depth>_DEEP`: the lid's outline, plus the plug outline inside it. Pocket the ring between them. The rabbet face is the underside, and the lid is drawn as seen from below.
- `DRILL_PILOT_<dia>_DIA_<depth>_DEEP`: optional pilot holes for the bracket screws, on the panels' inside faces. Panels too thin to screw into (1/4") get no pilots, and their brackets are glued.
- `LABELS_NOCUT` and `SHEET_48x96_NOCUT`: part names and the sheet outline. Don't toolpath these.

The file units are set in the DXF header (`$INSUNITS`). The sheet outline is 96 x 48 in, and parts stay 1/2" in from its edges with 1/2" between parts.

## Assumptions the brief left open

- Outside radius 75 mm by default (the reel's caption). The slider runs from 25 to 200 mm, with quick buttons for 50, 75 and 100.
- The bracket's look comes from the reel. The sizes are my choice: a 16 mm band, 22 mm wide along the corner, 40 mm flanges 5 mm thick, two 2 mm slots between three ribs, two 4.2 mm countersunk holes per flange, and a raised size marking.
- Screws: #8 flat-head wood screws, picked so they stop at least 3 mm short of the outside face.
- Skin thicknesses: 1/8", 1/4" or 3/8" flexible MDF. Panel thicknesses: 1/4", 1/2", 16 mm (the reel) or 3/4" MDF.
- Brackets per corner is a count, and they spread evenly between the end margins. With a lid, the top one moves up under the plug.
- The lid is MDF on the CNC, not printed, because a lid this size is far bigger than the printer bed.
- Nesting is simple shelf packing. VCarve Pro's own nesting may fit parts onto fewer sheets.

Written for Vincent Strader's shop. MIT licence.
