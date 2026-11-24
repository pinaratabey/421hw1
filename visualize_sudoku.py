"""Draw the assignment's starting grid or six grids supplied by the user."""

import argparse
import json
from pathlib import Path
from xml.etree import ElementTree as ET


START_GRID = [
    [2, 0, 0, 0, 6, 0, 0, 0, 0],
    [0, 5, 0, 0, 0, 1, 0, 0, 0],
    [7, 8, 0, 0, 4, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 6, 2, 9, 0, 0, 3],
    [0, 0, 0, 0, 5, 0, 0, 7, 0],
    [9, 0, 0, 0, 0, 3, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 9, 0, 0],
    [0, 0, 0, 2, 9, 0, 5, 0, 7],
]

METHODS = (
    "Backtracking",
    "Backtracking + Forward Checking",
    "Backtracking + MAC",
    "Backtracking + MRV",
    "Backtracking + Forward Checking + MRV",
    "Backtracking + MAC + MRV",
)

CELL = 32
BOARD = 9 * CELL
PANEL_WIDTH = 340
PANEL_HEIGHT = 340


def load_grids(path):
    """Read a JSON array of six 9-by-9 grids in assignment order."""
    grids = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(grids, list) or len(grids) != len(METHODS):
        raise ValueError("Expected a JSON array containing six grids.")

    for method, grid in zip(METHODS, grids):
        if not isinstance(grid, list) or len(grid) != 9:
            raise ValueError(f"{method}: expected nine rows.")
        for row in grid:
            if not isinstance(row, list) or len(row) != 9:
                raise ValueError(f"{method}: expected nine cells per row.")
            if any(type(value) is not int or not 0 <= value <= 9 for value in row):
                raise ValueError(f"{method}: cells must be integers from 0 to 9.")
    return grids


def draw_grid(svg, title, grid, left, top):
    panel = ET.SubElement(svg, "g", transform=f"translate({left} {top})")
    ET.SubElement(panel, "text", {
        "x": str(BOARD // 2), "y": "-12", "text-anchor": "middle",
        "font-size": "14", "font-weight": "600", "fill": "#13283d",
    }).text = title
    ET.SubElement(panel, "rect", width=str(BOARD), height=str(BOARD), fill="white")

    for r, row in enumerate(grid):
        for c, value in enumerate(row):
            x, y = c * CELL, r * CELL
            given = START_GRID[r][c] != 0 and value == START_GRID[r][c]
            if given:
                ET.SubElement(panel, "rect", x=str(x), y=str(y),
                              width=str(CELL), height=str(CELL), fill="#e4edf5")
            if value:
                ET.SubElement(panel, "text", {
                    "x": str(x + CELL // 2), "y": str(y + 23),
                    "text-anchor": "middle", "font-size": "20",
                    "font-weight": "700" if given else "400",
                    "fill": "#13283d" if given else "#274f72",
                }).text = str(value)

    # Give the outer frame and 3-by-3 block boundaries greater visual weight.
    for index in range(10):
        position = index * CELL
        major = index % 3 == 0
        ET.SubElement(panel, "path", {
            "d": f"M {position} 0 V {BOARD} M 0 {position} H {BOARD}",
            "fill": "none", "stroke": "#233d54" if major else "#9eafbf",
            "stroke-width": "2.2" if major else "0.8",
        })


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path,
                        help="JSON array of six grids in assignment order")
    parser.add_argument("--output", type=Path, default=Path("sudoku.svg"),
                        help="SVG output path (default: sudoku.svg)")
    args = parser.parse_args()

    if args.results is None:
        panels = [("Initial Sudoku Grid", START_GRID)]
        columns = 1
    else:
        try:
            grids = load_grids(args.results)
        except (OSError, ValueError) as exc:
            parser.error(str(exc))
        panels = list(zip(METHODS, grids))
        columns = 2

    rows = (len(panels) + columns - 1) // columns
    width, height = columns * PANEL_WIDTH, rows * PANEL_HEIGHT
    svg = ET.Element("svg", {
        "xmlns": "http://www.w3.org/2000/svg",
        "width": str(width), "height": str(height),
        "viewBox": f"0 0 {width} {height}", "font-family": "Arial, sans-serif",
        "role": "img",
    })
    description = "Initial Sudoku grid" if columns == 1 else "Six Sudoku grids"
    ET.SubElement(svg, "title").text = description
    ET.SubElement(svg, "rect", width=str(width), height=str(height), fill="white")
    for index, (title, grid) in enumerate(panels):
        row, column = divmod(index, columns)
        draw_grid(svg, title, grid, column * PANEL_WIDTH + 26, row * PANEL_HEIGHT + 36)

    try:
        ET.ElementTree(svg).write(args.output, encoding="utf-8", xml_declaration=True)
    except OSError as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
