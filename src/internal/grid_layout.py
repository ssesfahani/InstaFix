import os
import tempfile
from typing import List, Optional

import aiohttp
import networkx as nx
import pyvips

MAX_ROW_HEIGHT = 1000


def get_height(images_wh, canvas_width):
    """Calculate the height (in pixels) of a row that fits canvas_width."""
    # same logic as before: sum of (w/h) ratios
    ratio_sum = sum(w / h for w, h in images_wh)
    return canvas_width / ratio_sum


def cost_fn(images_wh, i, j, canvas_width):
    """Calculate cost of breaking images into a row."""
    row_height = get_height(images_wh[i:j], canvas_width)
    return (MAX_ROW_HEIGHT - row_height) ** 2


def create_graph(images_wh, start, canvas_width):
    """Create graph nodes with costs based on image layout."""
    results = {}
    for i in range(start + 1, min(start + 4, len(images_wh))):
        results[i] = cost_fn(images_wh, start, i, canvas_width)
    return results


def generate_grid(image_paths: List[str], out_fname: str) -> Optional[str]:
    """
    Given a list of file paths, lay them out in an optimal
    multi-row “justified” grid and write the result to out_fname.

    Returns out_fname on success, None on failure.
    """
    # 1) Load metadata
    im_meta = []
    for path in image_paths:
        img = pyvips.Image.new_from_file(path, access="sequential")
        im_meta.append((img.width, img.height))
    # sentinel to mark the "end" node
    im_meta.append((0, 0))

    # 2) Choose canvas width ~ average image width × a factor
    avg_w = sum(w for w, h in im_meta) / len(im_meta)
    canvas_w = int(avg_w * 1.5)

    # 3) Build graph of breakpoints with costs
    G = nx.DiGraph()
    n = len(im_meta) - 1  # last index is the sentinel
    for i in range(n):
        for j, cost in create_graph(im_meta, i, canvas_w).items():
            G.add_edge(i, j, weight=cost)

    # 4) Shortest‐path from 0 → n
    try:
        path = nx.shortest_path(G, 0, n, weight="weight")
    except nx.NetworkXNoPath:
        return None

    # 5) Compute each row height and total canvas height
    row_heights = []
    total_h = 0
    for u, v in zip(path, path[1:]):
        row_h = int(get_height(im_meta[u:v], canvas_w))
        row_heights.append(row_h)
        total_h += row_h

    # 6) Create a black RGB canvas
    # black() yields 1‐band; bandjoin → 3 bands (R=G=B=0)
    canvas = pyvips.Image.black(canvas_w, total_h).bandjoin(
        [pyvips.Image.black(canvas_w, total_h)] * 2
    )

    # 7) Composite each row of images
    y_offset = 0
    for (u, v), row_h in zip(zip(path, path[1:]), row_heights):
        x_offset = 0
        for idx in range(u, v):
            img = pyvips.Image.new_from_file(image_paths[idx], access="sequential")
            # scale factor so height → row_h
            scale = row_h / img.height
            img_resized = img.resize(scale)
            # insert into canvas at (x_offset, y_offset)
            canvas = canvas.insert(img_resized, x_offset, y_offset)
            x_offset += img_resized.width
        y_offset += row_h

    # 8) Save
    canvas.write_to_file(out_fname)
    return out_fname


async def grid_from_urls(urls: List[str], out_fname: str) -> Optional[str]:
    """Generate a grid image based on the best row layout."""
    images = []
    async with aiohttp.ClientSession() as session:
        for url in urls:
            async with session.get(url) as response:
                with tempfile.NamedTemporaryFile(suffix=".jpeg", delete=False) as f:
                    f.write(await response.read())
                    images.append(f.name)
    x = None
    try:
        x = generate_grid(images, out_fname)
    except:
        pass
    finally:
        for f in images:
            os.remove(f)
        return x
