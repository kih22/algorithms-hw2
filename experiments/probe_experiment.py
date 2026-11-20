"""Measure separate-chaining search costs over a range of load factors."""

import csv
import random
from pathlib import Path

from src.hash_table import HashTable

CAPACITY = 2003
LOAD_FACTORS = tuple(round(step / 4, 2) for step in range(1, 17))
TRIALS = 5
SEED = 2026
OUTPUT_DIR = Path(__file__).parent
_key_generator = random.Random(SEED)
KEYS = [
    f"url-{_key_generator.getrandbits(64):016x}"
    for _ in range(round(4 * CAPACITY))
]


def measure(load_factor: float) -> tuple[float, float]:
    item_count = round(load_factor * CAPACITY)
    keys = KEYS[:item_count]
    successful_probes = []
    unsuccessful_probes = []

    for trial in range(TRIALS):
        insertion_order = keys.copy()
        random.Random(SEED + trial).shuffle(insertion_order)
        table = HashTable(capacity=CAPACITY)
        for key in insertion_order:
            table[key] = key

        successful_probes.extend(table.probe_count(key) for key in keys)
        unsuccessful_probes.extend(
            table.probe_count(f"missing-{trial}-{index:08d}")
            for index in range(item_count)
        )

    return (
        sum(successful_probes) / len(successful_probes),
        sum(unsuccessful_probes) / len(unsuccessful_probes),
    )


def write_svg(rows: list[tuple[float, float, float]]) -> None:
    width, height = 760, 520
    left, top, plot_width, plot_height = 78, 40, 630, 360
    maximum = max(
        actual
        for row in rows
        for actual in (row[1], row[2], 1 + row[0] / 2, row[0])
    )
    y_max = max(1, int(maximum + 0.999))

    def point(load: float, probes: float) -> tuple[float, float]:
        x = left + load / 4 * plot_width
        y = top + plot_height - probes / y_max * plot_height
        return x, y

    series = (
        ("성공 실측", "#1769aa", 1),
        ("성공 이론 1+α/2", "#1769aa", 0),
        ("실패 실측", "#c62828", 2),
        ("실패 이론 α", "#c62828", 3),
    )
    data = {
        0: [(row[0], row[1]) for row in rows],
        1: [(row[0], 1 + row[0] / 2) for row in rows],
        2: [(row[0], row[2]) for row in rows],
        3: [(row[0], row[0]) for row in rows],
    }

    pieces = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<text x="380" y="24" text-anchor="middle" font-size="18">체이닝 해시 테이블 탐색 비용</text>',
    ]
    for tick in range(y_max + 1):
        y = top + plot_height - tick / y_max * plot_height
        pieces.append(f'<path d="M {left} {y:.1f} H {left + plot_width}" stroke="#ddd"/>')
        pieces.append(
            f'<text x="{left - 12}" y="{y + 4:.1f}" text-anchor="end" font-size="12">{tick}</text>'
        )
    for tick in range(9):
        load = tick * 0.5
        x = left + load / 4 * plot_width
        pieces.append(f'<path d="M {x:.1f} {top} V {top + plot_height}" stroke="#eee"/>')
        pieces.append(
            f'<text x="{x:.1f}" y="{top + plot_height + 20}" text-anchor="middle" font-size="12">{load:.1f}</text>'
        )
    pieces.extend(
        [
            f'<path d="M {left} {top} V {top + plot_height} H {left + plot_width}" fill="none" stroke="#333"/>',
            f'<text x="{left + plot_width / 2}" y="{top + plot_height + 48}" text-anchor="middle" font-size="14">적재율 α</text>',
            f'<text x="18" y="{top + plot_height / 2}" text-anchor="middle" font-size="14" transform="rotate(-90 18 {top + plot_height / 2})">평균 노드 탐색 횟수</text>',
        ]
    )
    for label, color, index in series:
        coordinates = " ".join(
            f"{x:.1f},{y:.1f}" for x, y in (point(*pair) for pair in data[index])
        )
        dash = ' stroke-dasharray="6 4"' if index in (1, 3) else ""
        pieces.append(
            f'<polyline points="{coordinates}" fill="none" stroke="{color}" stroke-width="2"{dash}/>'
        )
        legend_x = left + (index % 2) * 250
        legend_y = top + plot_height + 78 + (index // 2) * 22
        pieces.append(
            f'<path d="M {legend_x} {legend_y - 4} h 24" stroke="{color}" stroke-width="2"{dash}/>'
        )
        pieces.append(
            f'<text x="{legend_x + 32}" y="{legend_y}" font-size="12">{label}</text>'
        )
    pieces.append("</svg>")
    (OUTPUT_DIR / "probe_experiment.svg").write_text("\n".join(pieces), encoding="utf-8")


def main() -> None:
    rows = []
    for load_factor in LOAD_FACTORS:
        successful, unsuccessful = measure(load_factor)
        rows.append((load_factor, successful, unsuccessful))

    csv_path = OUTPUT_DIR / "probe_results.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.writer(output)
        writer.writerow(
            [
                "load_factor",
                "successful_measured",
                "successful_theory",
                "unsuccessful_measured",
                "unsuccessful_theory",
            ]
        )
        for load, successful, unsuccessful in rows:
            writer.writerow(
                [load, successful, 1 + load / 2, unsuccessful, load]
            )

    write_svg(rows)
    print(" α    성공 실측  성공 이론  실패 실측  실패 이론")
    for load, successful, unsuccessful in rows:
        print(
            f"{load:>3.2f}  {successful:>8.3f}  {1 + load / 2:>8.3f}"
            f"  {unsuccessful:>8.3f}  {load:>8.3f}"
        )
    print(f"\nWrote {csv_path.name} and probe_experiment.svg")


if __name__ == "__main__":
    main()
