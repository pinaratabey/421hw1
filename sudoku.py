
import argparse
from collections import deque
import json
from pathlib import Path
from statistics import median
from time import perf_counter_ns


# 0 marks an empty cell.
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

# Each method specifies its rules and MRV setting
METHODS = (
    # Go row by row and try digits that fit.
    ("Backtracking", "none", False),
    # Go row by row and remove each chosen digit from empty neighbors.
    ("Backtracking + Forward Checking", "fc", False),
    # Go row by row and pass candidate changes along to neighbors.
    ("Backtracking + MAC", "mac", False),
    # Pick the cell with the fewest choices and try digits that fit.
    ("Backtracking + MRV", "none", True),
    # Pick the cell with the fewest choices and check its empty neighbors.
    ("Backtracking + Forward Checking + MRV", "fc", True),
    # Pick the cell with the fewest choices and spread changes with MAC.
    ("Backtracking + MAC + MRV", "mac", True),
)

SIZE = 9
ALL_DIGITS = (1 << SIZE) - 1
POSITIONS = tuple((i // 9, i % 9, i // 27 * 3 + i % 9 // 3) for i in range(81))
# Neighbors share a row, column, or box.
PEERS = tuple(
    tuple(
        j for j, (other_row, other_col, other_box) in enumerate(POSITIONS)
        if i != j and (row == other_row or col == other_col or box == other_box)
    )
    for i, (row, col, box) in enumerate(POSITIONS)
)


# Find the first solution and count how many assignments we undo
def solve(grid, inference, use_mrv):
    if inference not in ("none", "fc", "mac"):
        raise ValueError("Unknown inference rule.")
    if len(grid) != SIZE or any(len(row) != SIZE for row in grid):
        raise ValueError("Expected a 9-by-9 grid.")
    board = [value for row in grid for value in row]
    # Each bit marks a digit that is already used.
    row_masks = [0] * SIZE
    col_masks = [0] * SIZE
    box_masks = [0] * SIZE
    empty = []
    backtracks = 0

    # Find digits unused in the row, column, and box
    def legal(cell):
        row, col, box = POSITIONS[cell]
        return ALL_DIGITS & ~(row_masks[row] | col_masks[col] | box_masks[box])

    # Find empty cells and check that the clues do not clash
    for cell, value in enumerate(board):
        if type(value) is not int or not 0 <= value <= SIZE:
            raise ValueError("Every cell must be an integer from 0 to 9.")
        if value == 0:
            empty.append(cell)
            continue
        bit = 1 << (value - 1)
        if not legal(cell) & bit:
            raise ValueError("Conflicting clues.")
        row, col, box = POSITIONS[cell]
        row_masks[row] |= bit
        col_masks[col] |= bit
        box_masks[box] |= bit

    # Use AC-3 to check how each candidate change affects its neighbors
    def maintain_arc_consistency(domains, queue):
        # If a neighbor has one candidate, rule it out here
        while queue:
            source, target = queue.popleft()
            target_domain = domains[target]
            if target_domain & (target_domain - 1):
                continue
            old_domain = domains[source]
            new_domain = old_domain & ~target_domain
            if new_domain == old_domain:
                continue
            if not new_domain:
                return False
            domains[source] = new_domain
            # A candidate was removed, so check the other neighbors again
            queue.extend((peer, source) for peer in PEERS[source] if peer != target)
        return True

    domains = None
    if inference != "none":
        # Save the starting candidates for forward checking and MAC
        domains = [
            1 << (value - 1) if value else legal(cell)
            for cell, value in enumerate(board)
        ]
        if not all(domains):
            return None, 0
        if inference == "mac":
            queue = deque((peer, cell) for cell in empty for peer in PEERS[cell])
            if not maintain_arc_consistency(domains, queue):
                return None, 0

    # Fill one cell at a time until the board is complete
    def search(remaining, current_domains):
        nonlocal backtracks
        if not remaining:
            return True
        domain_of = legal if current_domains is None else current_domains.__getitem__

        # Pick the first empty cell in row order
        cell = remaining[0]
        if use_mrv:
            # MRV picks the cell with the fewest candidates. Ties keep row order
            cell = min(remaining, key=lambda index: domain_of(index).bit_count())
        domain = domain_of(cell)
        if not domain:
            return False

        # LCV tries the digit that removes the fewest choices from neighbors
        peer_domains = [domain_of(peer) for peer in PEERS[cell] if board[peer] == 0]
        candidates = [
            (sum(bool(peer_domain & (1 << (value - 1))) for peer_domain in peer_domains),
             value)
            for value in range(1, SIZE + 1)
            if domain & (1 << (value - 1))
        ]
        next_remaining = [index for index in remaining if index != cell]
        row, col, box = POSITIONS[cell]
        # When two digits affect neighbors equally, try the smaller digit first
        for _, value in sorted(candidates):
            bit = 1 << (value - 1)
            board[cell] = value
            row_masks[row] |= bit
            col_masks[col] |= bit
            box_masks[box] |= bit

            consistent = True
            child_domains = None
            if current_domains is not None:
                # Copy the candidates so a failed try does not affect the next one
                child_domains = current_domains.copy()
                child_domains[cell] = bit
                if inference == "fc":
                    # Remove the chosen digit from empty neighbors
                    for peer in PEERS[cell]:
                        if board[peer] == 0:
                            child_domains[peer] &= ~bit
                            if not child_domains[peer]:
                                consistent = False
                                break
                else:
                    queue = deque((peer, cell) for peer in PEERS[cell])
                    consistent = maintain_arc_consistency(child_domains, queue)

            if consistent and search(next_remaining, child_domains):
                return True

            # Undo the assignment after a dead end
            board[cell] = 0
            row_masks[row] ^= bit
            col_masks[col] ^= bit
            box_masks[box] ^= bit
            # Count one backtrack each time we undo a failed assignment
            backtracks += 1
        return False

    if not search(empty, domains):
        return None, backtracks
    return [board[start:start + SIZE] for start in range(0, 81, SIZE)], backtracks


# Check the starting clues and the digits in every row, column, and box
def valid_solution(clues, solution):
    """Check all clues plus the 27 Sudoku units."""
    if solution is None or len(solution) != SIZE or any(len(row) != SIZE for row in solution):
        return False
    digits = set(range(1, SIZE + 1))
    for row, col, _ in POSITIONS:
        if clues[row][col] and clues[row][col] != solution[row][col]:
            return False
    for index in range(SIZE):
        box_row, box_col = divmod(index, 3)
        box_digits = {
            solution[row][col]
            for row in range(3 * box_row, 3 * box_row + 3)
            for col in range(3 * box_col, 3 * box_col + 3)
        }
        if set(solution[index]) != digits or {row[index] for row in solution} != digits:
            return False
        if box_digits != digits:
            return False
    return True


# Time each method several times and report the median
def benchmark(repeats):
    results = []
    for name, inference, use_mrv in METHODS:
        samples = []
        expected = None
        for _ in range(repeats):
            start = perf_counter_ns()
            solution, backtracks = solve(START_GRID, inference, use_mrv)
            samples.append((perf_counter_ns() - start) / 1_000_000)
            # Check the answer after stopping the timer.
            if not valid_solution(START_GRID, solution):
                raise RuntimeError(f"{name} returned an invalid solution.")
            if expected is not None and (solution, backtracks) != expected:
                raise RuntimeError(f"{name} produced inconsistent results.")
            expected = (solution, backtracks)
        results.append({
            "method": name, "solution": solution, "backtracks": backtracks,
            "median_ms": median(samples), "samples_ms": samples,
        })
    return results


# Read the options, run the methods, and print the results
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=7)
    parser.add_argument("--metrics", type=Path, help="Write timing and backtrack data to JSON.")
    parser.add_argument("--grids", type=Path, help="Write the six solutions to JSON.")
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("--repeats must be at least 1.")

    results = benchmark(args.repeats)
    print(f"{'Method':42} {'Median (ms)':>12} {'Backtracks':>11}")
    for result in results:
        print(f"{result['method']:42} {result['median_ms']:12.3f} {result['backtracks']:11d}")
    if args.metrics:
        args.metrics.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    if args.grids:
        grids = [result["solution"] for result in results]
        args.grids.write_text(json.dumps(grids, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
