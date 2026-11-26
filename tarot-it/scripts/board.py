"""Render a fixed Tarot-it result as an offline board and an optional PNG."""

from html import escape
from io import BytesIO


CROSS = [(1, 1), (1, 1), (1, 0), (1, 2), (0, 1), (2, 1), (3, 3), (3, 2), (3, 1), (3, 0)]
HORSESHOE = [(0, 2), (1, 1), (2, 0), (3, 0), (4, 0), (5, 1), (6, 2)]
STYLE = '''
:root {color-scheme:dark; background:#141823; color:#f7f0df; font:16px system-ui,sans-serif}
body {max-width:1120px; margin:0 auto; padding:1.5rem}
h1 {margin:0 0 .4rem; font-family:Georgia,serif}
p {color:#e3d5ba}
.board {list-style:none; padding:0; display:grid; gap:1rem; align-items:start; margin:2rem 0}
.board > li {grid-area:var(--row)/var(--col); min-width:0; position:relative}
.board > .crossing {z-index:1; margin-top:2.1rem}
.zoom {position:absolute; width:1px; height:1px; opacity:0}
.art {display:block; cursor:zoom-in; text-align:center}
.art img {display:block; width:100%; height:auto; max-width:180px; margin:auto;
    transform:rotate(var(--angle)); border-radius:.35rem; box-shadow:0 .2rem .8rem #0009}
.crossing .art img {transform:rotate(calc(var(--angle) + 90deg)) scale(.75)}
.zoom:focus-visible + .art {outline:2px solid #f4d18d; outline-offset:4px}
.zoom:checked + .art {position:fixed; inset:0; z-index:20; display:grid; place-content:center;
    cursor:zoom-out; background:#080a10f5; padding:1rem; gap:.75rem}
.zoom:checked + .art img {width:min(85vw,60vh); height:76vh; object-fit:contain;
    max-width:none; box-shadow:none; transform:rotate(var(--angle))}
.close {display:none}
.zoom:checked + .art .close {display:block}
.caption {margin:.5rem 0; overflow-wrap:anywhere; font-size:.9rem}
.caption small {color:#e3d5ba}
.crossing .caption {display:none}
.legend {margin:1.25rem 0; padding-left:1.5rem; line-height:1.65}
.inspect {color:#f4d18d; cursor:zoom-in; text-decoration:underline; white-space:nowrap}
footer {color:#e3d5ba; border-top:1px solid #555; padding-top:1rem; font-size:.86rem}
@media(max-width:720px) {
    .board {grid-template-columns:minmax(0,1fr) !important}
    .board > li,.board > .crossing {grid-area:auto; margin:0; max-width:100%; z-index:auto}
    .crossing .art img {transform:rotate(var(--angle))}
    .caption,.crossing .caption {display:block; text-align:center}
}
'''


def layout(spread, count):
    if spread == 'celtic-cross':
        return 4, CROSS
    if spread == 'horseshoe':
        return 7, HORSESHOE
    columns = 4 if spread == 'annual' else count
    return columns, [(index % columns, index // columns) for index in range(count)]


def labels(card):
    direction = '正位' if card['orientation'] == 'upright' else '逆位'
    return f'{card["position"]}. {card["label"]}', f'{card["name_zh"]} · {direction}', card['name_en']


def render_html(result, encoded_images, *, full_size=True):
    columns, cells = layout(result['spread'], len(result['cards']))
    cards, legend = [], []
    for card, encoded, (col, row) in zip(result['cards'], encoded_images, cells):
        first, second, english = map(escape, labels(card))
        number = card['position']
        angle = '180deg' if card['orientation'] == 'reversed' else '0deg'
        crossing = 'crossing' if result['spread'] == 'celtic-cross' and number == 2 else ''
        cards.append(f'''<li class="{crossing}" style="--row:{row + 1};--col:{col + 1};--angle:{angle}">
<input class="zoom" type="checkbox" id="card-{number}" aria-label="放大或缩小 {second}">
<label class="art" for="card-{number}"><img src="data:image/jpeg;base64,{encoded}" alt="{second}">
<span class="close">{first} · {second} · 点击关闭</span></label>
<p class="caption"><strong>{first}</strong><br>{second}<br><small>{english}</small></p></li>''')
        legend.append(f'<li>{escape(card["label"])} · {second} <small>({english})</small> '
                      f'<label class="inspect" for="card-{number}">放大牌面</label></li>')
    title = escape(result['spread_name'])
    help_text = '点击图片查看高清牌面。' if full_size else '点击图片放大完整牌面。此附件使用轻量图片。'
    return f'''<!doctype html>
<html lang="zh-Hans"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src data:; style-src 'unsafe-inline'">
<title>{title} · Tarot-it</title><style>{STYLE}</style>
<body><main><h1>{title}</h1><p>{help_text}通过 Tab 和空格也可放大。</p>
<ol class="board" style="grid-template-columns:repeat({columns},minmax(0,1fr))">{''.join(cards)}</ol>
<h2>牌位顺序</h2><ol class="legend">{''.join(legend)}</ol></main>
<footer>插画 Pamela Colman Smith · Rider–Waite–Smith（Pam-A）</footer></body></html>
'''


def render_overview(result, paths):
    if len(paths) <= 3:
        return None
    try:
        from PIL import Image, ImageDraw, ImageOps
    except ImportError:
        return None
    if not hasattr(Image, 'Resampling'):
        return None
    columns, cells = layout(result['spread'], len(paths))
    rows = max(y for _, y in cells) + 1
    cell_width, cell_height, padding = 172, 230, 18
    canvas = Image.new('RGB', (columns * cell_width + 2 * padding, rows * cell_height + 2 * padding), '#141823')
    draw = ImageDraw.Draw(canvas)
    for number, (path, (col, row)) in enumerate(zip(paths, cells), 1):
        with Image.open(path) as original:
            image = ImageOps.contain(original.convert('RGB'), (132, 196), Image.Resampling.LANCZOS)
        crossing = result['spread'] == 'celtic-cross' and number == 2
        if crossing:
            image = ImageOps.contain(image.transpose(Image.Transpose.ROTATE_270), (166, 104))
        x = padding + col * cell_width + (cell_width - image.width) // 2
        y = padding + row * cell_height + (196 - image.height) // 2
        canvas.paste(image, (x, y))
        label_y = y + image.height if crossing else padding + (row + 1) * cell_height - 21
        label_x = x + image.width - 32 if crossing else padding + col * cell_width + 66
        draw.rounded_rectangle((label_x, label_y, label_x + 32, label_y + 18), radius=3, fill='#2d3446')
        draw.text((label_x + 7, label_y + 2), f'{number:02}', fill='#fff4db')
    buffer = BytesIO()
    canvas.save(buffer, 'PNG', optimize=True)
    return buffer.getvalue()
