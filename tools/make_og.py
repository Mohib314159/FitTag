"""Link-preview image (docs/og.png) for LinkedIn/Slack/iMessage, built from the demo data."""
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
D = ROOT / "docs"
s = json.loads((D / "data" / "samples.json").read_text())[0]
W, H = 1200, 630
img = Image.new("RGB", (W, H), (243, 243, 240))
d = ImageDraw.Draw(img)
def font(sz, bold=True):
    for p in (["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"] if bold else ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]):
        try: return ImageFont.truetype(p, sz)
        except OSError: pass
    return ImageFont.load_default()
# tape rule
d.rectangle([0, 0, W, 16], fill=(242, 194, 48))
for x in range(0, W, 12): d.line([(x, 0), (x, 6 if x % 60 else 11)], fill=(22, 23, 27), width=2)
ph = Image.open(D / s["photo"]); fl = Image.open(D / s["flat"])
h = 530
ph = ph.resize((int(ph.width * h / ph.height), h)); fl = fl.resize((int(fl.width * h / fl.height), h))
k = h / s["flat_size"][1]
fd = ImageDraw.Draw(fl)
fd.line([(x * k, y * k) for x, y in s["outline"]] + [(s["outline"][0][0] * k, s["outline"][0][1] * k)], fill=(242, 194, 48), width=3)
for m in s["measurements"]:
    a = (m["p1"][0] * k, m["p1"][1] * k); b = (m["p2"][0] * k, m["p2"][1] * k)
    fd.line([a, b], fill=(255, 255, 255), width=6); fd.line([a, b], fill=(47, 91, 211), width=3)
img.paste(ph, (40, 56)); img.paste(fl, (40 + ph.width + 12, 56))
x0 = 40 + ph.width + 12 + fl.width + 32
d.text((x0, 70), "FitTag", font=font(56), fill=(22, 23, 27))
y = 160
for line in ["Measures secondhand", "clothes from one", "phone photo, in cm", "with error bars."]:
    d.text((x0, y), line, font=font(25, False), fill=(22, 23, 27)); y += 34
y += 20
for m in s["measurements"][:4]:
    d.text((x0, y), f'{m["name"].replace("_", " "):<12}', font=font(19, False), fill=(85, 87, 95))
    d.text((x0 + 135, y), f"{m['cm']:.1f} ± {m['tol']:.1f} cm", font=font(19), fill=(22, 23, 27)); y += 34
d.text((x0, H - 70), "mohib314159.github.io/FitTag", font=font(15, False), fill=(85, 87, 95))
img.save(D / "og.png", optimize=True)
print("docs/og.png", img.size)
