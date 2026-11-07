"""Slide 4 screens, cropped to the part that matters so the text can be read: python3 cards_en3.py <shots dir>
(shots from shoot_en3.js, 780 px wide = a 390 px phone at 2x). Writes img/c_<name>.png as rounded cards."""
import sys
from PIL import Image, ImageDraw

S = sys.argv[1].rstrip('/') + '/'
H = 900  # the same height for every card, so they line up
CROPS = {'c_gstin': ('02_gstin', 282), 'c_why': ('04_why', 40), 'c_kyc': ('07_kyc', 640),
         'c_tracker': ('11_tracker_live', 62), 'c_onebill': ('12_onebill', 180)}
R, LINE = 36, (229, 231, 235)
for name, (shot, top) in CROPS.items():
    im = Image.open(S + shot + '.png').convert('RGB')
    im = im.crop((0, top, 780, top + H))
    out = Image.new('RGBA', (780, H), (0, 0, 0, 0))
    mask = Image.new('L', (780, H), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, 779, H - 1), R, fill=255)
    out.paste(im, (0, 0), mask)
    ImageDraw.Draw(out).rounded_rectangle((0, 0, 779, H - 1), R, outline=LINE, width=3)
    out.save(f'img/{name}.png', optimize=True)
    print(name, out.size)
