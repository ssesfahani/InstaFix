from io import BytesIO
from typing import List, Optional

import aiohttp
import networkx as nx
from PIL import Image

MAX_ROW_HEIGHT = 1000


def get_height(images_wh, canvas_width):
    """Calculate row height for given image dimensions."""
    height_sum = sum(w / h for w, h in images_wh)
    return canvas_width / height_sum


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


def generate_grid(images: List[Image.Image], out_fname: str) -> Optional[str]:
    """Generate a grid image based on the best row layout."""
    images_wh = [(img.width, img.height) for img in images] + [(0, 0)]
    canvas_width = int(sum(w for w, _ in images_wh) / len(images_wh) * 1.5)

    G = nx.DiGraph()
    for i in range(len(images)):
        edges = create_graph(images_wh, i, canvas_width)
        for j, cost in edges.items():
            G.add_edge(i, j, weight=cost)

    try:
        path = nx.shortest_path(G, 0, len(images), weight="weight")
    except nx.NetworkXNoPath:
        return None

    canvas_height, row_heights = 0, []
    for i in range(1, len(path)):
        row_height = int(get_height(images_wh[path[i - 1] : path[i]], canvas_width))
        row_heights.append(row_height)
        canvas_height += row_height

    canvas = Image.new("RGB", (canvas_width, canvas_height))
    y_offset = 0

    for i in range(1, len(path)):
        row = images[path[i - 1] : path[i]]
        row_height = row_heights[i - 1]
        x_offset = 0

        for img in row:
            new_width = int(row_height * (img.width / img.height))
            img_resized = img.resize((new_width, row_height))
            canvas.paste(img_resized, (x_offset, y_offset))
            x_offset += new_width

        y_offset += row_height

    canvas.save(out_fname)
    return out_fname


async def grid_from_urls(urls: List[str], out_fname: str) -> Optional[str]:
    """Generate a grid image based on the best row layout."""
    images = []
    async with aiohttp.ClientSession() as session:
        for url in urls:
            async with session.get(url) as response:
                images.append(Image.open(BytesIO(await response.read())))
    return generate_grid(images, out_fname)
