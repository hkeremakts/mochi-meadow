"""A pixel-art critic for the drawn sprites: the classic mistakes, with
where they are.  After pxl's ``lint`` (github.com/uilianks/pxl, MIT).

    orphan   a lone pixel inside a shape, in a colour none of its
             neighbours share and barely different from them: noise, not
             detail (eye glints and noses are high-contrast, so they pass)
    jaggy    a doubled corner in a 1-px line: an L where the line should
             step diagonally
"""

N8 = ((-1, -1), (0, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (0, 1), (1, 1))


def _lum(c):
    return 0.0 if c is None else 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def _pixels(surface):
    w, h = surface.get_size()
    grid = [[None] * w for _ in range(h)]
    for y in range(h):
        for x in range(w):
            c = surface.get_at((x, y))
            if c.a:
                grid[y][x] = (c.r, c.g, c.b)
    return grid, w, h


def orphans(surface, contrast=48):
    grid, w, h = _pixels(surface)

    def get(x, y):
        return grid[y][x] if 0 <= x < w and 0 <= y < h else None
    out = []
    for y in range(h):
        for x in range(w):
            c = grid[y][x]
            if c is None or any(get(x + dx, y + dy) == c for dx, dy in N8):
                continue
            if any(get(x + dx, y + dy) is None for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1))):
                continue
            around = [get(x + dx, y + dy) for dx, dy in N8]
            if abs(_lum(c) - sum(_lum(a) for a in around) / 8) < contrast:
                out.append((x, y))
    return out


def jaggies(surface):
    grid, w, h = _pixels(surface)

    def get(x, y):
        return grid[y][x] if 0 <= x < w and 0 <= y < h else None
    # 8-connected strokes of one colour, 6+ pixels, with no 2x2 block: lines.
    comp, sizes, thin = {}, [], []
    for y0 in range(h):
        for x0 in range(w):
            c = grid[y0][x0]
            if c is None or (x0, y0) in comp:
                continue
            ident, stack, size, is_thin = len(sizes), [(x0, y0)], 0, True
            comp[(x0, y0)] = ident
            while stack:
                x, y = stack.pop()
                size += 1
                if get(x + 1, y) == c and get(x, y + 1) == c and get(x + 1, y + 1) == c:
                    is_thin = False
                for dx, dy in N8:
                    n = (x + dx, y + dy)
                    if get(*n) == c and n not in comp:
                        comp[n] = ident
                        stack.append(n)
            sizes.append(size)
            thin.append(is_thin)
    out = []
    for y in range(h):
        for x in range(w):
            c = grid[y][x]
            if c is None:
                continue
            ident = comp[(x, y)]
            if sizes[ident] < 6 or not thin[ident]:
                continue

            def same(dx, dy):
                return get(x + dx, y + dy) == c
            if sum(same(dx, dy) for dx, dy in N8) != 2:
                continue
            for hx, vy in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
                if same(hx, 0) and same(0, vy) and not same(hx, vy) and not same(2 * hx, 0) and not same(0, 2 * vy):
                    out.append((x, y))
                    break
    return out
