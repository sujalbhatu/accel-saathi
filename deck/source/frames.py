from PIL import Image, ImageDraw
S = 's2/'
CROPS = {'f_gstin': ('02_gstin', 0), 'f_wa': ('21_wa_bundle', 250), 'f_item': ('04_item', 0), 'f_kyc': ('23_kyc_verified', 300),
         'f_wastatus': ('24_wa_status', 330), 'f_onebill': ('12_onebill', 0), 'f_tracker': ('11_tracker_live', 0),
         'f_consent': ('06_consent', 300), 'f_bundle': ('03_bundle', 340)}
H, BEZEL, R = 1340, 18, 70
for name, (shot, top) in CROPS.items():
    im = Image.open(S + shot + '.png').convert('RGB')
    top = min(top, im.height - H)
    im = im.crop((0, top, 780, top + H))
    W2, H2 = 780 + 2 * BEZEL, H + 2 * BEZEL
    out = Image.new('RGBA', (W2, H2), (0, 0, 0, 0))
    d = ImageDraw.Draw(out)
    d.rounded_rectangle((0, 0, W2 - 1, H2 - 1), R, fill=(28, 28, 34, 255))
    mask = Image.new('L', (780, H), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, 779, H - 1), R - BEZEL, fill=255)
    out.paste(im, (BEZEL, BEZEL), mask)
    out = out.resize((W2 * 2 // 3, H2 * 2 // 3), Image.LANCZOS)
    out.save(f'img/{name}.png', optimize=True)
names = list(CROPS)
ims = [Image.open(f'img/{n}.png').resize((272, 458)) for n in names]
g = Image.new('RGB', (280 * len(ims), 460), 'white')
for i, im in enumerate(ims): g.paste(im, (i * 280, 0), im)
g.save('s2/frames_grid.png')
