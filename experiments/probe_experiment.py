"""Measure separate-chaining search costs over a range of load factors."""

import csv
import random
from math import ceil
from pathlib import Path

from src.hash_table import HashTable

CAPACITY = 4093
TARGET_LOAD_FACTORS = tuple(step / 4 for step in range(1, 17))
TRIALS = 5
SEED = 2026
OUTPUT_DIR = Path(__file__).parent
CSV_PATH = OUTPUT_DIR / "results.csv"
SVG_PATH = OUTPUT_DIR / "probe_experiment.svg"
MAX_ITEMS = round(4 * CAPACITY)


def make_urls(count: int, seed: int) -> list[str]:
    """Create reproducible URL-shaped keys with randomized hosts."""
    generator = random.Random(seed)
    return [
        f"https://{generator.getrandbits(64):016x}.example.test/record/{index:05d}"
        for index in range(count)
    ]


URLS = make_urls(MAX_ITEMS, SEED)


def measure(target_load_factor: float) -> tuple[float, int, float, float]:
    item_count = round(target_load_factor * CAPACITY)
    actual_load_factor = item_count / CAPACITY
    keys = URLS[:item_count]
    successful_probes = 0
    unsuccessful_probes = 0
    query_count = 0

    for trial in range(TRIALS):
        insertion_order = keys.copy()
        random.Random(SEED + trial).shuffle(insertion_order)

        # HashTable has fixed capacity and never resizes, equivalent to max_load=None.
        table = HashTable(capacity=CAPACITY)
        for key in insertion_order:
            table[key] = key

        successful_probes += sum(table.probe_count(key) for key in keys)
        missing_urls = make_missing_urls(item_count, trial)
        unsuccessful_probes += sum(
            table.probe_count(url) for url in missing_urls
        )
        query_count += item_count

    return (
        actual_load_factor,
        item_count,
        successful_probes / query_count,
        unsuccessful_probes / query_count,
    )


def make_missing_urls(count: int, trial: int) -> list[str]:
    """Create absent URL keys from a host namespace not used by inserted URLs."""
    generator = random.Random(SEED + 100 + trial)
    return [
        f"https://missing-{generator.getrandbits(64):016x}.example.test/query/{index:05d}"
        for index in range(count)
    ]


def write_csv(rows: list[tuple[float, float, int, float, float]]) -> None:
    with CSV_PATH.open("w", newline="", encoding="utf-8") as output:
        writer = csv.writer(output, lineterminator="\n")
        writer.writerow(
            [
                "target_load_factor",
                "actual_load_factor",
                "item_count",
                "capacity",
                "trials",
                "successful_measured_nodes",
                "successful_theory_nodes",
                "unsuccessful_measured_nodes",
                "unsuccessful_theory_nodes",
            ]
        )
        for target_load, actual_load, item_count, successful, unsuccessful in rows:
            writer.writerow(
                [
                    target_load,
                    actual_load,
                    item_count,
                    CAPACITY,
                    TRIALS,
                    successful,
                    1 + actual_load / 2,
                    unsuccessful,
                    actual_load,
                ]
            )


def write_svg(rows: list[tuple[float, float, int, float, float]]) -> None:
    width, height = 800, 570
    left, top, plot_width, plot_height = 82, 52, 660, 350
    maximum = max(
        value
        for _, load, _, successful, unsuccessful in rows
        for value in (successful, unsuccessful, 1 + load / 2, load)
    )
    y_max = max(1, ceil(maximum))

    def point(load: float, probes: float) -> tuple[float, float]:
        x = left + load / 4 * plot_width
        y = top + plot_height - probes / y_max * plot_height
        return x, y

    series = (
        ("성공 실측", "#1769aa", [(row[1], row[3]) for row in rows], False),
        (
            "성공 이론 1+α/2",
            "#1769aa",
            [(row[1], 1 + row[1] / 2) for row in rows],
            True,
        ),
        ("실패 실측", "#c62828", [(row[1], row[4]) for row in rows], False),
        ("실패 이론 α", "#c62828", [(row[1], row[1]) for row in rows], True),
    )
    pieces = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<text x="400" y="25" text-anchor="middle" font-size="18">체이닝 해시 테이블 탐색 비용</text>',
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
    for index, (label, color, values, dashed) in enumerate(series):
        coordinates = " ".join(
            f"{x:.1f},{y:.1f}" for x, y in (point(*pair) for pair in values)
        )
        dash = ' stroke-dasharray="6 4"' if dashed else ""
        pieces.append(
            f'<polyline points="{coordinates}" fill="none" stroke="{color}" stroke-width="2"{dash}/>'
        )
        legend_x = left + (index % 2) * 300
        legend_y = top + plot_height + 78 + (index // 2) * 22
        pieces.append(
            f'<path d="M {legend_x} {legend_y - 4} h 24" stroke="{color}" stroke-width="2"{dash}/>'
        )
        pieces.append(
            f'<text x="{legend_x + 32}" y="{legend_y}" font-size="12">{label}</text>'
        )
    pieces.append(
        f'<text x="{left}" y="{height - 12}" font-size="11">버킷 {CAPACITY}개 · 적재율당 {TRIALS}회 · 시드 {SEED} · 재현 가능한 무작위 URL</text>'
    )
    pieces.append("</svg>")
    SVG_PATH.write_text("\n".join(pieces), encoding="utf-8")


def main() -> None:
    rows = []
    for target_load_factor in TARGET_LOAD_FACTORS:
        actual_load, item_count, successful, unsuccessful = measure(
            target_load_factor
        )
        rows.append(
            (target_load_factor, actual_load, item_count, successful, unsuccessful)
        )

    write_csv(rows)
    write_svg(rows)

    print("목표 α  실제 α    항목 수  성공 실측  성공 이론  실패 실측  실패 이론")
    for target_load, actual_load, item_count, successful, unsuccessful in rows:
        print(
            f"{target_load:>5.2f}  {actual_load:>6.3f}  {item_count:>8}"
            f"  {successful:>8.3f}  {1 + actual_load / 2:>8.3f}"
            f"  {unsuccessful:>8.3f}  {actual_load:>8.3f}"
        )

    max_success_error = max(
        abs(successful - (1 + actual_load / 2))
        for _, actual_load, _, successful, _ in rows
    )
    max_failure_error = max(
        abs(unsuccessful - actual_load)
        for _, actual_load, _, _, unsuccessful in rows
    )
    print(
        "\n최대 절대 오차: "
        f"성공 {max_success_error:.3f}, 실패 {max_failure_error:.3f}"
    )
    print(
        "작은 차이는 유한한 URL 표본과 버킷별 충돌 분포에 따른 측정 변동입니다."
    )
    print(f"Wrote {CSV_PATH.name} and {SVG_PATH.name}")


if __name__ == "__main__":
    main()
