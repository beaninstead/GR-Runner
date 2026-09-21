import os

import pygame

try:
    import numpy as np
except ImportError:
    np = None

from future_run.animation import Animation
from future_run.constants import (
    GRADDIE_SIZE,
    GROUND_TOP,
    LOGICAL_H,
    LOGICAL_W,
    OUTLINE,
    PLAYER_H,
    PLAYER_W,
    S,
    TILE,
    WHITE,
)
from future_run.web import IS_WEB

# Bundled Press Start 2P — path relative to project root (parent of future_run/)
_FONT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "fonts",
    "PressStart2P.ttf",
)


PLAYER_KEY = (93, 171, 253)
PLAYER_FRAMES = 9
# Legacy square cell size; new player sheets derive frame size from image dims.
PLAYER_CELL = 111
GRADDIE_FRAMES = 4
AGENT_FRAMES = 4
FALSE_INFO_FRAMES = 4


def load_image(path, colorkey=None, alpha=False):
    image = pygame.image.load(path)
    if alpha or path.lower().endswith(".png"):
        image = image.convert_alpha()
    else:
        image = image.convert()
    if colorkey is not None:
        if colorkey == -1:
            colorkey = image.get_at((0, 0))[:3]
        image.set_colorkey(colorkey, pygame.RLEACCEL)
    return image


def _rgba(image):
    if np is None:
        return image, None, None
    image = image.convert_alpha()
    rgb = pygame.surfarray.array3d(image).astype(np.int16)
    alpha = pygame.surfarray.array_alpha(image).astype(np.int16)
    return image, rgb, alpha


def _write_rgba(image, rgb, alpha):
    pygame.surfarray.blit_array(image, np.clip(rgb, 0, 255).astype(np.uint8))
    alpha_px = pygame.surfarray.pixels_alpha(image)
    alpha_px[:] = np.clip(alpha, 0, 255).astype(np.uint8)
    del alpha_px
    return image


def _ensure_rgba(image):
    """Force a true 32-bit SRCALPHA surface (palette/P-mode PNGs need this)."""
    return image.convert_alpha()


def _knockout_black_fallback(image, max_rgb_sum=0):
    """Remove black matte without numpy (web/pygbag ships with np=None).

    Optimized palette sheets often lose tRNS; opaque black then fills each
    frame cell and fit_box_bottom shrinks the character into a tall strip.
    Exact (0,0,0) uses colorkey blit; max_rgb_sum>0 also clears near-black.
    """
    image = _ensure_rgba(image)
    if max_rgb_sum <= 0:
        keyed = image.copy()
        keyed.set_colorkey((0, 0, 0))
        out = pygame.Surface(image.get_size(), pygame.SRCALPHA)
        out.blit(keyed, (0, 0))
        return out
    out = image.copy()
    w, h = out.get_size()
    for x in range(w):
        for y in range(h):
            r, g, b, a = out.get_at((x, y))
            if a and (r + g + b) <= max_rgb_sum:
                out.set_at((x, y), (0, 0, 0, 0))
    return out


def knockout_color(image, key, threshold=36, fade=22):
    """Remove a chroma key by writing alpha. Colorkey is ignored on SRCALPHA."""
    image = _ensure_rgba(image)
    if np is None:
        key = tuple(key)[:3]
        if key == (0, 0, 0):
            return _knockout_black_fallback(image, max_rgb_sum=max(0, threshold // 3))
        keyed = image.copy()
        keyed.set_colorkey(key)
        out = pygame.Surface(image.get_size(), pygame.SRCALPHA)
        out.blit(keyed, (0, 0))
        return out
    image, rgb, alpha = _rgba(image)
    key = np.array(key, dtype=np.int16)
    dist = np.abs(rgb - key).sum(axis=2)
    kill = dist <= threshold
    soft = (~kill) & (dist <= threshold + fade)
    alpha[kill] = 0
    if fade > 0 and np.any(soft):
        t = (dist[soft].astype(np.float32) - threshold) / float(fade)
        alpha[soft] = (alpha[soft].astype(np.float32) * t).astype(np.int16)
        # Despill leftover key color on the fringe.
        mix = 1.0 - t
        rgb[soft] = np.clip(
            rgb[soft] - (key * mix[:, None] * 0.55), 0, 255
        ).astype(np.int16)
    return _write_rgba(image, rgb, alpha)


def _dilate4(mask):
    """4-connected dilation for boolean (width, height) arrays."""
    out = mask.copy()
    out[1:, :] |= mask[:-1, :]
    out[:-1, :] |= mask[1:, :]
    out[:, 1:] |= mask[:, :-1]
    out[:, :-1] |= mask[:, 1:]
    return out


def knockout_player_matte(image, chroma_min=10, luma_core=48, luma_keep=12):
    """Knock out black/JPEG matte without eating navy, hair, shoes, or outlines.

    Chromatic or bright pixels seed the sprite. The mask then grows only through
    non-matte neighbors so dark suit/shoe pixels stay, while true black (and
    disconnected JPEG crumbs) become transparent. Kept RGB is never altered.
    """
    image = _ensure_rgba(image)
    if np is None:
        # Exact black only — preserves navy suit / hair / shoes on web.
        return _knockout_black_fallback(image, max_rgb_sum=0)
    image, rgb, alpha = _rgba(image)
    luma = rgb[:, :, 0].astype(np.int32) + rgb[:, :, 1] + rgb[:, :, 2]
    chroma = rgb.max(axis=2) - rgb.min(axis=2)
    keep = (chroma >= chroma_min) | (luma >= luma_core)
    walkable = luma > luma_keep
    for _ in range(64):
        grown = _dilate4(keep) & walkable
        if np.array_equal(grown, keep):
            break
        keep = grown | keep
    alpha[~keep] = 0
    return _write_rgba(image, rgb, alpha)


def knockout_edge_dark(image, luma=22):
    """Drop near-black pixels that touch transparency (JPEG / matte fringe)."""
    if np is None:
        return image
    image, rgb, alpha = _rgba(image)
    opaque = alpha > 16
    dark = opaque & (rgb.sum(axis=2) <= luma * 3)
    if not np.any(dark):
        return image
    trans = alpha <= 16
    neighbor = np.zeros(trans.shape, dtype=bool)
    neighbor[1:, :] |= trans[:-1, :]
    neighbor[:-1, :] |= trans[1:, :]
    neighbor[:, 1:] |= trans[:, :-1]
    neighbor[:, :-1] |= trans[:, 1:]
    neighbor[0, :] = True
    neighbor[-1, :] = True
    neighbor[:, 0] = True
    neighbor[:, -1] = True
    drop = dark & neighbor
    alpha[drop] = 0
    return _write_rgba(image, rgb, alpha)


def drop_specks(image, min_opaque_neighbors=1):
    if np is None:
        return image
    image, rgb, alpha = _rgba(image)
    opaque = alpha > 40
    count = np.zeros(opaque.shape, dtype=np.int16)
    count[1:, :] += opaque[:-1, :]
    count[:-1, :] += opaque[1:, :]
    count[:, 1:] += opaque[:, :-1]
    count[:, :-1] += opaque[:, 1:]
    specks = opaque & (count < min_opaque_neighbors)
    alpha[specks] = 0
    return _write_rgba(image, rgb, alpha)


def add_outline(image, color=OUTLINE):
    if np is None:
        return image
    image, rgb, alpha = _rgba(image)
    opaque = alpha > 80
    edge = np.zeros(opaque.shape, dtype=bool)
    edge[1:, :] |= opaque[:-1, :]
    edge[:-1, :] |= opaque[1:, :]
    edge[:, 1:] |= opaque[:, :-1]
    edge[:, :-1] |= opaque[:, 1:]
    paint = edge & ~opaque
    rgb[paint] = np.array(color, dtype=np.int16)
    alpha[paint] = 255
    return _write_rgba(image, rgb, alpha)


def trim_alpha(image, pad=2):
    mask = pygame.mask.from_surface(image)
    rects = mask.get_bounding_rects()
    if not rects:
        return image
    bounds = rects[0]
    for extra in rects[1:]:
        bounds.union_ip(extra)
    bounds.inflate_ip(pad * 2, pad * 2)
    bounds.clamp_ip(image.get_rect())
    cropped = pygame.Surface(bounds.size, pygame.SRCALPHA)
    cropped.blit(image, (0, 0), bounds)
    return cropped


def _largest_opaque_mask(opaque):
    """4-connected component mask for the largest opaque blob (w,h bool)."""
    w, h = opaque.shape
    labels = np.zeros((w, h), dtype=np.int32)
    sizes = {}
    label = 0
    for x in range(w):
        for y in range(h):
            if not opaque[x, y] or labels[x, y]:
                continue
            label += 1
            stack = [(x, y)]
            labels[x, y] = label
            size = 0
            while stack:
                cx, cy = stack.pop()
                size += 1
                for nx, ny in (
                    (cx - 1, cy),
                    (cx + 1, cy),
                    (cx, cy - 1),
                    (cx, cy + 1),
                ):
                    if (
                        0 <= nx < w
                        and 0 <= ny < h
                        and opaque[nx, ny]
                        and labels[nx, ny] == 0
                    ):
                        labels[nx, ny] = label
                        stack.append((nx, ny))
            sizes[label] = size
    if not sizes:
        return opaque
    best = max(sizes, key=sizes.get)
    return labels == best


def crop_main_content(image, pad=0, alpha_threshold=40):
    """
    Keep the largest opaque 2D blob, then tight content bbox + pad.

    Neighbor-frame bleed (suitcase wheels, jacket slivers) is usually a
    separate connected component inside an equal-width/valley cell; discarding
    everything but the main sprite removes it before scale-up.

    Uses pygame.mask so web (no numpy) still drops bleed shards.
    """
    mask = pygame.mask.from_surface(image, threshold=alpha_threshold)
    if mask.count() == 0:
        return trim_alpha(image, pad=pad)
    keep = mask.connected_component()
    if keep.count() == 0:
        return trim_alpha(image, pad=pad)
    cleaned = keep.to_surface(setsurface=image, unsetcolor=(0, 0, 0, 0))
    return trim_alpha(cleaned, pad=pad)


def scale_nearest(image, size):
    size = (max(1, int(size[0])), max(1, int(size[1])))
    return pygame.transform.scale(image, size)


def fit_height(image, height):
    w, h = image.get_size()
    if h <= 0:
        return image
    scale = height / h
    return scale_nearest(image, (w * scale, height))


def fit_width(image, width):
    w, h = image.get_size()
    if w <= 0:
        return image
    scale = width / w
    return scale_nearest(image, (width, h * scale))


def fit_box_bottom(image, size):
    """Scale to fit inside size, centered horizontally and bottom-aligned."""
    box_w, box_h = size
    w, h = image.get_size()
    if w <= 0 or h <= 0:
        return pygame.Surface(size, pygame.SRCALPHA)
    scale = min(box_w / w, box_h / h)
    nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
    scaled = scale_nearest(image, (nw, nh))
    out = pygame.Surface(size, pygame.SRCALPHA)
    out.blit(scaled, ((box_w - nw) // 2, box_h - nh))
    return out


def slice_row(sheet, count, frame_w, frame_h, y=0, inset=0):
    """Equal-width cells; optional left/right inset avoids neighbor-frame bleed."""
    inset = max(0, int(inset))
    frames = []
    for i in range(count):
        cell_w = max(1, frame_w - 2 * inset)
        surf = pygame.Surface((cell_w, frame_h), pygame.SRCALPHA)
        surf.blit(
            sheet,
            (0, 0),
            pygame.Rect(i * frame_w + inset, y, cell_w, frame_h),
        )
        frames.append(surf)
    return frames


def _opaque_column_flags(sheet, alpha_threshold=40):
    """Bool per column: any opaque pixel. Works without numpy (web/pygbag)."""
    if np is not None:
        alpha = pygame.surfarray.array_alpha(sheet)
        return np.any(alpha > alpha_threshold, axis=1)
    mask = pygame.mask.from_surface(sheet, threshold=alpha_threshold)
    w, h = sheet.get_size()
    strip = pygame.mask.Mask((1, h), fill=True)
    return [bool(mask.overlap(strip, (x, 0))) for x in range(w)]


def _opaque_column_counts(sheet, alpha_threshold=40):
    """Opaque pixel count per column. Works without numpy (web/pygbag)."""
    if np is not None:
        alpha = pygame.surfarray.array_alpha(sheet)
        return np.count_nonzero(alpha > alpha_threshold, axis=1).astype(np.int32)
    mask = pygame.mask.from_surface(sheet, threshold=alpha_threshold)
    w, h = sheet.get_size()
    counts = [0] * w
    for x in range(w):
        n = 0
        for y in range(h):
            if mask.get_at((x, y)):
                n += 1
        counts[x] = n
    return counts


def _opaque_column_runs(sheet, alpha_threshold=40, merge_gap=3, min_width=4):
    """Return inclusive (x0, x1) spans of opaque columns, merging thin gaps."""
    cols = _opaque_column_flags(sheet, alpha_threshold=alpha_threshold)
    runs = []
    in_run = False
    start = 0
    width = len(cols)
    for x in range(width):
        if cols[x] and not in_run:
            in_run = True
            start = x
        elif not cols[x] and in_run:
            in_run = False
            runs.append([start, x - 1])
    if in_run:
        runs.append([start, width - 1])
    if not runs:
        return []
    if min_width > 1:
        runs = [r for r in runs if r[1] - r[0] + 1 >= min_width]
        if not runs:
            return []
    merged = [runs[0]]
    for x0, x1 in runs[1:]:
        prev = merged[-1]
        if x0 - prev[1] - 1 <= merge_gap:
            prev[1] = x1
        else:
            merged.append([x0, x1])
    return [(a, b) for a, b in merged]


def _valley_frame_bounds(sheet, count, alpha_threshold=40, search=18, edge_pad=8):
    """
    Split a packed row into `count` frames at column-density valleys.

    Used when sprites touch or jump+dead merge so blob counting != count.
    Cuts sit at local minima near equal-content boundaries.
    """
    colsum = _opaque_column_counts(sheet, alpha_threshold=alpha_threshold)
    opaque = [i for i, n in enumerate(colsum) if n > 0]
    if not opaque:
        return []
    x0 = opaque[0]
    x1 = opaque[-1]
    span = x1 - x0 + 1
    if span < count:
        return []
    cuts = [x0]
    for i in range(1, count):
        ideal = x0 + int(round(i * span / count))
        lo = max(x0 + edge_pad, ideal - search)
        hi = min(x1 - edge_pad, ideal + search)
        if lo >= hi:
            cuts.append(ideal)
        else:
            window = colsum[lo : hi + 1]
            best = 0
            best_v = window[0]
            for j, v in enumerate(window):
                if v < best_v:
                    best_v = v
                    best = j
            cuts.append(lo + best)
    cuts.append(x1 + 1)
    bounds = []
    for i in range(count):
        a, b = cuts[i], cuts[i + 1] - 1
        if b >= a:
            bounds.append((a, b))
    return bounds if len(bounds) == count else []


def _blit_x_spans(sheet, spans, y, frame_h, inset=0):
    """Copy inclusive x-spans from sheet into frame surfaces, with side inset."""
    inset = max(0, int(inset))
    frames = []
    for x0, x1 in spans:
        a = x0 + inset
        b = x1 - inset
        if b < a:
            a, b = x0, x1
        fw = max(1, b - a + 1)
        surf = pygame.Surface((fw, frame_h), pygame.SRCALPHA)
        surf.blit(sheet, (0, 0), pygame.Rect(a, y, fw, frame_h))
        frames.append(surf)
    return frames


def slice_row_blobs(sheet, count, y=0, alpha_threshold=40, merge_gap=3):
    """
    Content-aware horizontal split: one frame per opaque column blob.

    If blob count mismatches (touching sprites / merged jump+dead), split at
    column-density valleys. Last resort: equal-width cells with side inset.

    Uses pygame.mask column scans when numpy is missing (web) — equal-width
    fallback alone causes neighbor-frame ghosting on packed sheets.
    """
    sheet_w, sheet_h = sheet.get_size()
    frame_h = sheet_h - y
    runs = _opaque_column_runs(sheet, alpha_threshold=alpha_threshold, merge_gap=merge_gap)
    if len(runs) == count:
        # Inset strips contact crumbs / suitcase wheels at blob edges.
        return _blit_x_spans(sheet, runs, y, frame_h, inset=4)
    valley = _valley_frame_bounds(
        sheet, count, alpha_threshold=alpha_threshold
    )
    if len(valley) == count:
        # Inset so valley contact pixels shared by neighbors are discarded.
        return _blit_x_spans(sheet, valley, y, frame_h, inset=5)
    frame_w = max(1, sheet_w // count)
    return slice_row(sheet, count, frame_w, frame_h, y=y, inset=8)


def load_player_sheet(path, preserve_dark=False):
    """Knock out black matte, content-aware split, tight crop, fit, outline.

    Sheet layout: idle, run1-4, crouch, jump, jump2, dead.
    preserve_dark keeps navy/hair/shoe pixels that a black chroma-key would eat.
    """
    sheet = _ensure_rgba(load_image(path, alpha=True))
    if preserve_dark:
        sheet = knockout_player_matte(sheet)
        sheet = drop_specks(sheet)
    else:
        sheet = knockout_color(sheet, (0, 0, 0), threshold=28, fade=12)
        sheet = knockout_edge_dark(sheet, luma=14)
    small = slice_row_blobs(sheet, PLAYER_FRAMES, y=0)
    names = [
        "idle",
        "run1",
        "run2",
        "run3",
        "run4",
        "break",
        "jump",
        "jump2",
        "dead",
    ]
    frames = {}
    for name, frame in zip(names, small):
        # pad=0: closer crop — less neighbor-frame bleed after half-res + quantize.
        frame = crop_main_content(frame, pad=0)
        frame = fit_box_bottom(frame, (PLAYER_W, PLAYER_H))
        frames[name] = add_outline(frame, (42, 28, 22))
    return frames


def load_agent_sheet(path):
    """4-pose study-abroad agent: preserve dark hair/pants, split, crop, fit."""
    sheet = load_image(path, alpha=True)
    sheet = knockout_player_matte(sheet)
    sheet = drop_specks(sheet)
    small = slice_row_blobs(sheet, AGENT_FRAMES, y=0)
    box = (PLAYER_W, PLAYER_H)
    frames = []
    for frame in small:
        frame = crop_main_content(frame, pad=2)
        frame = fit_box_bottom(frame, box)
        frames.append(add_outline(frame, (42, 28, 22)))
    return frames


def load_false_info_sheet(path, height):
    """4-frame spinning newspaper: keep black ink, knock out exterior matte."""
    sheet = load_image(path, alpha=True)
    sheet = knockout_player_matte(sheet)
    sheet = drop_specks(sheet)
    small = slice_row_blobs(sheet, FALSE_INFO_FRAMES, y=0)
    frames = []
    for frame in small:
        frame = crop_main_content(frame, pad=2)
        frame = fit_height(frame, height)
        frames.append(add_outline(frame))
    return frames


def load_money_trap(path, height):
    """Thief/manhole prop: full sprite (cash + manhole), black matte keyed out.

    Do not use crop_main_content — knockout can split dark clothing from the
    cover, and keeping only the largest blob crops to a manhole fragment.
    """
    image = load_image(path, alpha=True)
    image = knockout_color(image, (0, 0, 0), threshold=28, fade=10)
    image = knockout_edge_dark(image, luma=14)
    image = drop_specks(image)
    image = trim_alpha(image, pad=2)
    image = fit_height(image, height)
    return add_outline(image)


def clean_prop(path, height, outline=True, extra_keys=None):
    image = load_image(path, alpha=True)
    w, h = image.get_size()
    keys = list(extra_keys or [])
    for x, y in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)):
        pixel = image.get_at((x, y))
        if pixel[3] > 200 and sum(pixel[:3]) < 36:
            keys.append(pixel[:3])
    seen = set()
    for key in keys:
        if key in seen:
            continue
        seen.add(key)
        image = knockout_color(image, key, threshold=14, fade=8)
    image = knockout_edge_dark(image, luma=16)
    image = drop_specks(image)
    image = trim_alpha(image, pad=2)
    image = fit_height(image, height)
    if outline:
        image = add_outline(image)
    return image


def load_prop_as_is(path, height, outline=True):
    """Scale a prop without knockout/trim so file pixels (incl. black) stay intact."""
    image = load_image(path, alpha=True)
    image = fit_height(image, height)
    if outline:
        image = add_outline(image)
    return image


def clean_button(path):
    """Knock out black matte and trim padding so UI buttons fill their rects."""
    image = load_image(path, alpha=True)
    image = knockout_color(image, (0, 0, 0), threshold=28, fade=10)
    image = knockout_edge_dark(image, luma=14)
    return trim_alpha(image, pad=2)


def solid_tile(image, size, fill=None):
    image = trim_alpha(image, pad=0)
    scaled = scale_nearest(image, (size, size))
    if fill is None:
        cx, cy = size // 2, int(size * 0.62)
        fill = scaled.get_at((min(cx, size - 1), min(cy, size - 1)))[:3]
        if scaled.get_at((cx, cy))[3] < 80:
            fill = (118, 72, 38)
    out = pygame.Surface((size, size))
    out.fill(fill)
    out.blit(scaled, (0, 0))
    return out.convert()


class Assets:
    def __init__(self):
        # World 1 backpack kid; Worlds 2–3 passport suit; World 4 trophy suit.
        self.player = load_player_sheet("img/player.png")
        self.player_world2 = load_player_sheet(
            "img/player_world2.png", preserve_dark=True
        )
        self.player_world3 = self.player_world2
        self.player_world4 = load_player_sheet("img/player_world4.png")
        # Study-abroad agent NPC (World 2): 4-pose writing/glance sheet.
        # Index 2 (front write) is the default facing pose for the idle cycle.
        self.agent = load_agent_sheet("img/future_run/agent.png")
        self.agent_idle = self.agent[2]

        # 4-frame sheet: idle, jump, land, victory (equal-width cells; keep cell
        # layout so the jump pose stays elevated within the box).
        graddie_sheet = load_image("img/graddie.png", alpha=True)
        graddie_sheet = knockout_color(graddie_sheet, (0, 0, 0), threshold=28, fade=12)
        graddie_sheet = knockout_edge_dark(graddie_sheet, luma=14)
        gw, gh = graddie_sheet.get_size()
        gfw = max(1, gw // GRADDIE_FRAMES)
        raw_graddie = slice_row(graddie_sheet, GRADDIE_FRAMES, gfw, gh, 0)
        box = (GRADDIE_SIZE, GRADDIE_SIZE)
        self.graddie = [fit_box_bottom(frame, box) for frame in raw_graddie]

        self.logo_white = fit_width(
            load_image("img/brand/gr_logo_white.png", colorkey=(0, 0, 0)), S(720)
        )
        self.logo_color = fit_width(
            load_image("img/brand/gr_logo_color.png", colorkey=(0, 0, 0)), S(720)
        )

        sky = load_image("img/future_run/pack_sky.png", alpha=True)
        ground_src = load_image("img/future_run/ground_mid.png", alpha=True)
        ground_src = knockout_color(ground_src, (0, 0, 0), threshold=16, fade=8)
        left_src = load_image("img/future_run/ground_left.png", alpha=True)
        left_src = knockout_color(left_src, (0, 0, 0), threshold=16, fade=8)
        right_src = load_image("img/future_run/ground_right.png", alpha=True)
        right_src = knockout_color(right_src, (0, 0, 0), threshold=16, fade=8)
        brick_src = load_image("img/future_run/pack_brick.png", alpha=True)
        brick_src = knockout_color(brick_src, (0, 0, 0), threshold=16, fade=8)
        question_src = load_image("img/future_run/pack_question.png", alpha=True)
        question_src = knockout_color(question_src, (0, 0, 0), threshold=16, fade=8)

        self.tiles = {
            "sky": scale_nearest(sky, (TILE, TILE)),
            "ground": solid_tile(ground_src, TILE, fill=(118, 72, 38)),
            "ground_left": solid_tile(left_src, TILE, fill=(118, 72, 38)),
            "ground_right": solid_tile(right_src, TILE, fill=(118, 72, 38)),
            "brick": solid_tile(brick_src, TILE, fill=(176, 64, 48)),
            "question": solid_tile(question_src, TILE, fill=(232, 176, 48)),
        }

        self.cloud1 = clean_prop("img/future_run/cloud1.png", int(TILE * 1.7), outline=False)
        self.cloud2 = clean_prop("img/future_run/cloud2.png", int(TILE * 1.35), outline=False)
        self.bush = clean_prop("img/future_run/pack_bush.png", int(TILE * 1.25))
        self.board = clean_prop("img/future_run/board.png", int(TILE * 1.85))
        self.plant = clean_prop("img/future_run/bush.png", int(TILE * 2.0))
        self.bench = clean_prop("img/future_run/bench.png", int(TILE * 1.25))
        self.bike = clean_prop("img/future_run/bike.png", int(TILE * 1.55))
        self.books = clean_prop("img/future_run/books_tall.png", int(TILE * 1.1))
        self.books_short = clean_prop("img/future_run/books_short.png", int(TILE * 0.75))
        self.skill_barrier = clean_prop(
            "img/future_run/skill_barrier.png", int(TILE * 1.1)
        )
        self.false_info = load_false_info_sheet(
            "img/future_run/false_info.png", int(TILE * 0.85)
        )
        self.money_trap = load_money_trap(
            "img/future_run/money_trap.png", int(TILE * 1.15)
        )
        self.phones = [
            clean_prop("img/future_run/phone1.png", int(TILE * 1.15)),
            clean_prop("img/future_run/phone2.png", int(TILE * 1.15)),
        ]
        self.blob_blue = clean_prop("img/future_run/blob_blue.png", int(TILE * 1.1))
        self.blob_purple = clean_prop("img/future_run/blob_purple.png", int(TILE * 1.1))
        self.alarm_clock = clean_prop("img/future_run/alarm_clock.png", int(TILE * 1.1))
        self.confusion_cloud = clean_prop(
            "img/future_run/confusion_cloud.png", int(TILE * 1.1)
        )
        self.paper_stack = clean_prop(
            "img/future_run/paper_stack.png", int(TILE * 1.1)
        )
        # FOMO billboard (used near the FOMO quiz)
        self.fomo_board = clean_prop(
            "img/future_run/fomo_sign.png", int(TILE * 3.2), outline=False
        )
        self.coins = [
            clean_prop(f"img/future_run/coin{i}.png", int(TILE * 0.9), outline=False)
            for i in range(4)
        ]
        self.gate = clean_prop("img/future_run/gate.png", int(TILE * 3.6), outline=False)
        self.flag = clean_prop("img/future_run/flag.png", int(TILE * 3.8), outline=False)

        title = load_image("img/future_run/pack_title.png", alpha=True)
        title = knockout_color(title, (0, 0, 0), threshold=24, fade=10)
        title = knockout_edge_dark(title, luma=12)
        self.title = fit_width(trim_alpha(title, pad=4), S(520))

        self.btn_start = clean_button("img/future_run/pack_btn_start.png")
        self.btn_continue = clean_button("img/future_run/pack_btn_continue.png")
        self.btn_retry = clean_button("img/future_run/pack_btn_retry.png")
        self.btn_home = clean_button("img/future_run/pack_btn_home.png")
        self.btn_cta = clean_button("img/future_run/pack_btn_cta.png")
        self.hud_heart = scale_nearest(
            trim_alpha(
                knockout_color(
                    load_image("img/future_run/pack_hud_heart.png", alpha=True),
                    (0, 0, 0),
                    threshold=24,
                    fade=8,
                )
            ),
            (S(80), S(80)),
        )
        self.hud_coin = scale_nearest(
            trim_alpha(
                knockout_color(
                    load_image("img/future_run/pack_hud_coin.png", alpha=True),
                    (0, 0, 0),
                    threshold=24,
                    fade=8,
                )
            ),
            (S(80), S(80)),
        )
        self.win_panel = load_image("img/future_run/pack_win_panel.png", alpha=True)
        self.game_over_panel = load_image("img/future_run/pack_game_over_panel.png", alpha=True)

        # Full-bleed win/end backdrop (same aspect as LOGICAL_W x LOGICAL_H).
        end_bg = load_image("img/future_run/end_screen_bg.jpg")
        self.end_screen_bg = scale_nearest(end_bg, (LOGICAL_W, LOGICAL_H))
        # Cream stats frame; scaled to content in Screens.win().
        self.win_stats_panel = load_image(
            "img/future_run/win_stats_panel.png", alpha=True
        )

        def _clean_ui(path):
            image = load_image(path, alpha=True)
            image = knockout_color(image, (0, 0, 0), threshold=28, fade=10)
            image = knockout_edge_dark(image, luma=14)
            return trim_alpha(image, pad=1)

        self.quiz_panel = _clean_ui("img/future_run/quiz_panel.png")
        self.quiz_option = _clean_ui("img/future_run/quiz_option.png")
        self.quiz_option_correct = _clean_ui("img/future_run/quiz_option_correct.png")
        self.quiz_option_wrong = _clean_ui("img/future_run/quiz_option_wrong.png")
        # Gold/cream frame for Ask-Graddie correct-option hint.
        self.quiz_option_hint = _clean_ui("img/future_run/quiz_option_hint.png")
        self.quiz_message = _clean_ui("img/future_run/quiz_message.png")
        # Pre-trimmed ask-helper banner (Graddie + white text panel).
        self.ask_graddie = load_image("img/future_run/ask_graddie.png", alpha=True)

        # World-specific skyline panoramas: scale to GROUND_TOP, keep aspect.
        # Drawn as a single scrolling strip (not tiled) — art edges do not match.
        # Web half-res ~2.4k×768; World may H-stretch slightly if level is longer.
        self.backdrops = {}
        for key, path in (
            ("world1", "img/future_run/bg_world1.png"),
            ("world2", "img/future_run/bg_world2.png"),
            ("world3", "img/future_run/bg_world3.png"),
            ("world4", "img/future_run/bg_world4.png"),
        ):
            self.backdrops[key] = fit_height(load_image(path, alpha=True), GROUND_TOP)

        if not os.path.isfile(_FONT_PATH):
            raise FileNotFoundError("Missing UI font: {}".format(_FONT_PATH))
        self.font_path = _FONT_PATH
        self._font_cache = {}
        # Press Start 2P is ~1.7× wider than VCR OSD Mono at the same px size.
        self.font_xl = self.font(S(40))
        self.font_lg = self.font(S(28))
        self.font_md = self.font(S(22))
        self.font_sm = self.font(S(16))
        self.font_xs = self.font(S(12))

    def font(self, size):
        """Return a cached pygame.font.Font for Press Start 2P at the given size."""
        size = int(size)
        cached = self._font_cache.get(size)
        if cached is None:
            cached = pygame.font.Font(self.font_path, size)
            self._font_cache[size] = cached
        return cached

    def tile(self, name, size=TILE):
        img = self.tiles.get(name)
        if img is None:
            img = self.tiles["ground"]
        if size != TILE:
            return pygame.transform.scale(img, (size, size))
        return img

    def coin_anim(self):
        return Animation(list(self.coins), deltaTime=8)

    def box_anim(self):
        frames = [self.tiles["question"]] * 3
        return Animation(frames, deltaTime=20)

    def draw_pixels(self, surf, text, x, y, size=18, color=WHITE):
        img = self.font(size).render(text, True, color)
        surf.blit(img, (x, y))
        return x + img.get_width()

    def draw_pixels_center(self, surf, text, y, size=18, color=WHITE):
        img = self.font(size).render(text, True, color)
        surf.blit(img, ((LOGICAL_W - img.get_width()) // 2, y))
