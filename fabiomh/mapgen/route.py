"""Path from the player to the exit to the next area (config.ROUTE_TARGETS), over the mapgen collision.

- Destination: the exit object with `id` = destination area; without it, the border passage to that area
  (objects.edge_exits, for transitions between outdoor areas). If it lands on a non-walkable cell (cave doors),
  it goes to the closest walkable one.
- 8-connected Dijkstra (diagonal only if both side cells are walkable, so as not to cut corners) **from the exit**,
  once per map (scipy.sparse.csgraph, ~75 ms on a 400×400 map; it stays in map_cache together with the meta).
  The predecessors point to the exit, so the path from any position is just following them (< 1 ms per tick).
- Cost of each step: distance × (1 + WALL_WEIGHT / distance to the wall), average of the two cells (symmetric graph).
  It keeps the path away from the walls, through the middle of the corridors; measured in Stony Field: 10–20% longer
  than the straight line.
- The player can be on a cell marked as non-walkable (or outside the exit's component): the trace starts at the
  closest reachable cell.
- Everything in the area's local coordinates, like the markers (objects.py).
"""
import numpy as np  # type: ignore
from scipy import ndimage, sparse  # type: ignore
from scipy.sparse import csgraph  # type: ignore

from config import ROUTE_TARGETS
from fabiomh.log import report
from fabiomh.mapgen.objects import edge_exits

# How much the path avoids the walls (0 = the shortest, hugging the corners)
WALL_WEIGHT = 4

# Neighbors (dy, dx) in one direction only: the graph is undirected
STEPS = ((0, 1), (1, 0), (1, 1), (1, -1))


class Route:
    def __init__(self, width, predecessors, reachable):
        self.width = width
        self.predecessors = predecessors
        self.reachable = reachable
        self.reachable_ys, self.reachable_xs = np.nonzero(reachable)

    def trace(self, x, y):
        """Local [(x, y)], from (x, y) to the exit, only with the vertices where the direction changes."""
        cx, cy = self.nearest(int(x), int(y))
        cells = []
        index = cy * self.width + cx
        while index >= 0:
            cells.append((index % self.width, index // self.width))
            index = int(self.predecessors[index])  # Python int: the points go to the Selenium JSON

        # Keeps the first, the last and the cells where the step changes direction
        path = [(x, y), cells[0]]
        for prev, cell, nxt in zip(cells, cells[1:], cells[2:]):
            if (cell[0] - prev[0], cell[1] - prev[1]) != (nxt[0] - cell[0], nxt[1] - cell[1]):
                path.append(cell)
        if len(cells) > 1:
            path.append(cells[-1])
        return path

    def nearest(self, x, y):
        height, width = self.reachable.shape
        if 0 <= x < width and 0 <= y < height and self.reachable[y, x]:
            return x, y
        i = np.argmin((self.reachable_xs - x) ** 2 + (self.reachable_ys - y) ** 2)
        return int(self.reachable_xs[i]), int(self.reachable_ys[i])


def build_route(level, grid, act_levels):
    """Route to the exit of ROUTE_TARGETS[area], or None (area without a configured destination or exit not found)."""
    target_level = ROUTE_TARGETS.get(level["id"])
    if target_level is None:
        return None

    target = find_target(level, grid, act_levels, target_level)
    if target is None:
        report("rota", f"área {level['id']}: saída para {target_level} não achada")
        return None
    report("rota", None)
    return route_to(grid, target)


def route_to(grid, target):
    """Route to the local point `target` (x, y), over the collision."""
    walkable = grid.astype(bool)
    height, width = walkable.shape
    tx, ty = nearest_walkable(walkable, *target)

    graph = build_graph(walkable)
    distances, predecessors = csgraph.dijkstra(graph, directed=False, indices=ty * width + tx,
                                               return_predecessors=True)
    reachable = np.isfinite(distances).reshape(height, width)
    return Route(width, predecessors.astype(np.int32), reachable)


def find_target(level, grid, act_levels, target_level):
    for obj in level["objects"]:
        if obj["type"] == "exit" and obj["id"] == target_level:
            return obj["x"], obj["y"]

    if target_level in act_levels:
        edge = edge_exits(level, grid, act_levels[target_level])
        if edge:
            return edge[0]
    return None


def nearest_walkable(walkable, x, y):
    height, width = walkable.shape
    x, y = min(max(x, 0), width - 1), min(max(y, 0), height - 1)
    if walkable[y, x]:
        return x, y
    ys, xs = np.nonzero(walkable)
    i = np.argmin((xs - x) ** 2 + (ys - y) ** 2)
    return int(xs[i]), int(ys[i])


def build_graph(walkable):
    """Sparse matrix (cells × cells) with the cost of the steps between neighboring walkable cells."""
    height, width = walkable.shape
    cost = 1 + WALL_WEIGHT / np.maximum(ndimage.distance_transform_edt(walkable), 1)
    rows, cols, weights = [], [], []

    for dy, dx in STEPS:
        # Origins (y, x) whose neighbor (y + dy, x + dx) is inside the map
        x_lo, x_hi = max(0, -dx), width - max(0, dx)
        ys, xs = np.nonzero(walkable[:height - dy, x_lo:x_hi])
        xs = xs + x_lo
        ny, nx = ys + dy, xs + dx

        ok = walkable[ny, nx]
        if dy and dx:
            ok &= walkable[ys, nx] & walkable[ny, xs]
        ys, xs, ny, nx = ys[ok], xs[ok], ny[ok], nx[ok]

        rows.append(ys * width + xs)
        cols.append(ny * width + nx)
        weights.append(np.hypot(dy, dx) * (cost[ys, xs] + cost[ny, nx]) / 2)

    size = height * width
    return sparse.csr_matrix((np.concatenate(weights), (np.concatenate(rows), np.concatenate(cols))),
                             shape=(size, size))
