import sys, math, tempfile, atexit, shutil
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import astro_hibou_core as C

# A scratch dir of our own: the test only needs somewhere to write a throwaway
# .seq, and hard-coding one ties the test to a machine that may not have it.
TMP = Path(tempfile.mkdtemp(prefix="test_quarantine_"))
atexit.register(shutil.rmtree, TMP, True)

def seq(matrices, selected=None):
    """Build a .seq like Siril writes it."""
    n = len(matrices)
    sel = selected or [1]*n
    L = ["#Siril sequence file.", f"S 'pp_t_' 1 {n} {n} 5 0 7 0 0 0", "L 1"]
    L += [f"I {i+1} {sel[i]}" for i in range(n)]
    for m in matrices:
        L.append("R0 5.0 5.0 0.9 0 0.001 60 H " + " ".join(str(v) for v in m))
    p = TMP/"t_.seq"; p.write_text("\n".join(L)+"\n"); return p

I = [1,0,0, 0,1,0, 0,0,1]
def rot(deg, w=3008):
    a=math.radians(deg); c,s=math.cos(a),math.sin(a); cx=cy=w/2
    # rotation about the image centre
    return [c,-s, cx-c*cx+s*cy,  s,c, cy-s*cx-c*cy, 0,0,1]
def shift(dx,dy): return [1,0,dx, 0,1,dy, 0,0,1]

# The real matrices Siril produced for pp_ha_ (reference = frame 1)
HA = [I,
      [0.708327,-0.706682,1491.96, 0.70628,0.708387,-620.13, 3.65045e-08,1.52068e-08,1],
      [0.70877,-0.707016,1524.58, 0.706478,0.7086,-622.575, 3.89568e-09,1.24576e-07,1]]

def run(name, matrices, selected=None, w=3008, h=3008):
    frames = C.read_seq_registration(seq(matrices, selected))
    assert len(frames) == len(matrices), f"{name}: parsed {len(frames)}"
    out = C.find_framing_outliers(frames, w, h)
    guard = len(out) > C.QUARANTINE_MAX_OUTLIER_FRAC * len(frames)
    verdict = "REFUSE (not a minority)" if guard else (f"dispose {sorted(out)}" if out else "clean")
    print(f"{name:38} -> {verdict}")
    for i,r in sorted(out.items()): print(f"      frame {i}: {r}")
    return out, guard

print("=== real data ===")
out,guard = run("real pp_ha_ (1 rogue of 3)", HA)
assert out and not guard and set(out)=={1}, "must flag the pre-gap frame 1 only"

print("\n=== synthetic ===")
out,g = run("2 frames, identity (green)", [I,I]);            assert not out
out,g = run("6 frames, 1 rotated 44.9", [rot(44.9)]+[I]*5);  assert set(out)=={1} and not g
out,g = run("6 frames, rogue is the ref", [I]+[rot(44.9)]*5); assert set(out)=={1} and not g
out,g = run("4 frames, 2v2 split",        [I,I,rot(44.9),rot(44.9)]); assert g, "guard must refuse"
out,g = run("5 frames, dither only",      [I,shift(8,-6),shift(-11,4),shift(3,9),shift(-5,-2)]); assert not out
out,g = run("5 frames, 1 big shift",      [I,I,I,I,shift(900,0)]);    assert set(out)=={5} and not g
out,g = run("5 frames, 1 unregistered",   [I]*5, selected=[1,1,0,1,1]); assert set(out)=={3} and not g
out,g = run("5 frames, slow drift 0.3deg",[rot(0),rot(.1),rot(.2),rot(.3),rot(.15)]); assert not out

print("\nALL ASSERTIONS PASSED")
