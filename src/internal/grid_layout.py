import heapq
import os
import tempfile
from collections import defaultdict
from typing import List, Optional

import aiohttp
import pyvips

MAX_ROW_HEIGHT = 1000


def dijkstra(graph, start, end):
    heap = [(0, start, [])]  # (cost, current_node, path)
    visited = set()

    while heap:
        cost, node, path = heapq.heappop(heap)
        if node in visited:
            continue
        visited.add(node)
        path = path + [node]
        if node == end:
            return path
        for neighbor, weight in graph.get(node, []):
            if neighbor not in visited:
                heapq.heappush(heap, (cost + weight, neighbor, path))
    return []


def get_jpeg_dimensions(file_path):
    with open(file_path, "rb") as file:
        # Skip the first two bytes (JPEG SOI marker)
        file.seek(2)

        while True:
            # Read marker
            marker = file.read(2)

            # EOF check
            if len(marker) < 2:
                raise ValueError("Invalid JPEG file or dimensions not found")

            # Check if we've reached a Start Of Frame marker (SOFn)
            # SOF0 (0xFFC0), SOF1 (0xFFC1), SOF2 (0xFFC2), etc.
            marker_code = (marker[0] << 8) + marker[1]
            is_sof = (
                (marker_code >= 0xFFC0 and marker_code <= 0xFFC3)
                or (marker_code >= 0xFFC5 and marker_code <= 0xFFC7)
                or (marker_code >= 0xFFC9 and marker_code <= 0xFFCB)
                or (marker_code >= 0xFFCD and marker_code <= 0xFFCF)
            )

            if is_sof:
                # Skip segment length and precision bytes
                file.seek(3, 1)

                # Read height and width (big-endian)
                height_bytes = file.read(2)
                width_bytes = file.read(2)

                height = (height_bytes[0] << 8) + height_bytes[1]
                width = (width_bytes[0] << 8) + width_bytes[1]

                return width, height
            else:
                # Skip to the next marker
                # First, get segment length
                length_bytes = file.read(2)
                if len(length_bytes) < 2:
                    raise ValueError("Invalid JPEG file or dimensions not found")

                # Length includes the 2 bytes for the length field itself
                length = (length_bytes[0] << 8) + length_bytes[1] - 2

                # Skip to the next marker
                file.seek(length, 1)


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
        img_width, img_height = get_jpeg_dimensions(path)
        im_meta.append((img_width, img_height))
    # sentinel to mark the "end" node
    im_meta.append((0, 0))

    # 2) Choose canvas width ~ average image width × a factor
    avg_w = sum(w for w, h in im_meta) / len(im_meta)
    canvas_w = int(avg_w * 1.5)

    # 3) Build graph of breakpoints with costs
    graph = defaultdict(list)
    n = len(im_meta) - 1  # last index is the sentinel
    for i in range(n):
        for j, cost in create_graph(im_meta, i, canvas_w).items():
            graph[i].append((j, cost))

    # 4) Shortest‐path from 0 → n
    path = dijkstra(graph, 0, n)

    # 5) Compute each row height and total canvas height
    row_heights = []
    total_h = 0
    for u, v in zip(path, path[1:]):
        row_h = int(get_height(im_meta[u:v], canvas_w))
        row_heights.append(row_h)
        total_h += row_h

    # 6) Create a black RGB canvas
    # black() yields 1‐band; bandjoin -> 3 bands (R=G=B=0)
    canvas = pyvips.Image.black(canvas_w, total_h).bandjoin(
        [pyvips.Image.black(canvas_w, total_h)] * 2
    )

    # 7) Composite each row of images
    y_offset = 0
    for (u, v), row_h in zip(zip(path, path[1:]), row_heights):
        x_offset = 0
        for idx in range(u, v):
            img = pyvips.Image.new_from_file(image_paths[idx], access="sequential")
            # scale factor so height -> row_h
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

    try:
        return generate_grid(images, out_fname)
    except Exception as e:
        raise e
    finally:
        for f in images:
            os.remove(f)
