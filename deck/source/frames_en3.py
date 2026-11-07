"""Phone frames for the deck from the shoot_en3.js screenshots: python3 frames_en3.py <shots dir>"""
import sys
from PIL import Image, ImageDraw

S = sys.argv[1].rstrip('/') + '/'
CROPS = {'e_gstin': ('02_gstin', 0), 'e_pains': ('03_pains', 0), 'e_why': ('04_why', 0), 'e_kyc': ('07_kyc', 0),
         'e_tracker': ('11_tracker_live', 0), 'e_onebill': ('12_onebill', 0), 'e_price': ('20_price', 0),
         'e_think': ('22_think', 0), 'e_competitor': ('21_competitor', 0)}
H, BEZEL, R = 1340, 18, 70
for name, (shot, top) in CROPS.items():
    im = Image.open(S + shot + '.png').convert('RGB')
    top = min(top, im.height - H)
    im = im.crop((0, top, 780, top + H))
    W2, H2 = 780 + 2 * BEZEL, H + 2 * BEZEL
    out = Image.new('RGBA', (W2, H2), (0, 0, 0, 0))
    ImageDraw.Draw(out).rounded_rectangle((0, 0, W2 - 1, H2 - 1), R, fill=(28, 28, 34, 255))
    mask = Image.new('L', (780, H), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, 779, H - 1), R - BEZEL, fill=255)
    out.paste(im, (BEZEL, BEZEL), mask)
    out = out.resize((W2 * 2 // 3, H2 * 2 // 3), Image.LANCZOS)
    out.save(f'img/{name}.png', optimize=True)
    print(name, out.size)
