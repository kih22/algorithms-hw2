"""Compare separate chaining and linear probing on the same URL workloads."""

import csv
import random
from dataclasses import dataclass
from math import ceil
from pathlib import Path

from src.hash_table import HashTable
from src.linear_probing import LinearProbingHashTable

CAPACITY = 4093
TARGET_LOAD_FACTORS = tuple(step / 10 for step in range(1, 10))
TRIALS = 5
SEED = 2026
OUTPUT_DIR = Path(__file__).parent
CSV_PATH = OUTPUT_DIR / "comparison_results.csv"
SVG_PATH = OUTPUT_DIR / "comparison_experiment.svg"


@dataclass(frozen=True)
class LoadMeasurement:
    target_load_factor: float
    actual_load_factor: float
    item_count: int
    capacity: int
    trials: int
    chaining_successful: float
    chaining_unsuccessful: float
    linear_successful: float
    linear_unsuccessful: float


def _make_keys(count: int, seed: int) -> list[str]:
    generator = random.Random(seed)
    return [
        f"https://{generator.getrandbits(64):016x}.example.test/record/{index:05d}"
        for index in range(count)
    ]


def _make_missing_keys(count: int, trial: int, seed: int) -> list[str]:
    generator = random.Random(seed + 100 + trial)
    return [
        f"https://missing-{generator.getrandbits(64):016x}.example.test/query/{index:05d}"
        for index in range(count)
    ]


def measure_load_factors(
    target_load_factors: tuple[float, ...] = TARGET_LOAD_FACTORS,
    capacity: int = CAPACITY,
    trials: int = TRIALS,
    seed: int = SEED,
) -> list[LoadMeasurement]:
    if capacity <= 0 or trials <= 0:
        raise ValueError("capacity and trials must be positive")
    if any(not 0 < load < 1 for load in target_load_factors):
        raise ValueError("target load factors must be between 0 and 1")

    max_items = round(max(target_load_factors) * capacity)
    keys = _make_keys(max_items, seed)
    results = []
    for target_load in target_load_factors:
        item_count = round(target_load * capacity)
        actual_load = item_count / capacity
        workload = keys[:item_count]
        chaining_successful = 0
        chaining_unsuccessful = 0
        linear_successful = 0
        linear_unsuccessful = 0

        for trial in range(trials):
            insertion_order = workload.copy()
            random.Random(seed + trial).shuffle(insertion_order)
            chained = HashTable[str](capacity=capacity)
            linear = LinearProbingHashTable[str](capacity=capacity)
            for key in insertion_order:
                chained[key] = key
                linear[key] = key

            missing_keys = _make_missing_keys(item_count, trial, seed)
            chaining_successful += sum(chained.probe_count(key) for key in workload)
            linear_successful += sum(linear.probe_count(key) for key in workload)
            chaining_unsuccessful += sum(
                chained.probe_count(key) for key in missing_keys
            )
            linear_unsuccessful += sum(
                linear.probe_count(key) for key in missing_keys
            )

        query_count = item_count * trials
        results.append(
            LoadMeasurement(
                target_load_factor=target_load,
                actual_load_factor=actual_load,
                item_count=item_count,
                capacity=capacity,
                trials=trials,
                chaining_successful=chaining_successful / query_count,
                chaining_unsuccessful=chaining_unsuccessful / query_count,
                linear_successful=linear_successful / query_count,
                linear_unsuccessful=linear_unsuccessful / query_count,
            )
        )
    return results


def _linear_theory(load: float) -> tuple[float, float]:
    return (
        0.5 * (1 + 1 / (1 - load)),
        0.5 * (1 + 1 / ((1 - load) ** 2)),
    )


def write_csv(rows: list[LoadMeasurement]) -> None:
    with CSV_PATH.open("w", newline="", encoding="utf-8") as output:
        writer = csv.writer(output, lineterminator="\n")
        writer.writerow(
            [
                "target_load_factor",
                "actual_load_factor",
                "item_count",
                "capacity",
                "trials",
                "chaining_successful_measured",
                "chaining_successful_theory",
                "chaining_unsuccessful_measured",
                "chaining_unsuccessful_theory",
                "linear_successful_measured",
                "linear_successful_theory",
                "linear_unsuccessful_measured",
                "linear_unsuccessful_theory",
            ]
        )
        for row in rows:
            linear_successful_theory, linear_unsuccessful_theory = _linear_theory(
                row.actual_load_factor
            )
            writer.writerow(
                [
                    row.target_load_factor,
                    row.actual_load_factor,
                    row.item_count,
                    row.capacity,
                    row.trials,
                    row.chaining_successful,
                    1 + row.actual_load_factor / 2,
                    row.chaining_unsuccessful,
                    row.actual_load_factor,
                    row.linear_successful,
                    linear_successful_theory,
                    row.linear_unsuccessful,
                    linear_unsuccessful_theory,
                ]
            )


def write_svg(rows: list[LoadMeasurement]) -> None:
    width, height = 980, 650
    left, top, plot_width, plot_height = 88, 55, 820, 390
    linear_theories = [_linear_theory(row.actual_load_factor) for row in rows]
    maximum = max(
        value
        for row, theory in zip(rows, linear_theories)
        for value in (
            row.chaining_successful,
            row.chaining_unsuccessful,
            row.linear_successful,
            row.linear_unsuccessful,
            1 + row.actual_load_factor / 2,
            row.actual_load_factor,
            theory[0],
            theory[1],
        )
    )
    y_max = ceil(maximum)

    def point(load: float, probes: float) -> tuple[float, float]:
        x = left + load / 0.9 * plot_width
        y = top + plot_height - probes / y_max * plot_height
        return x, y

    series = (
        ("체이닝 성공 실측", "#1769aa", [r.chaining_successful for r in rows], False),
        ("체이닝 성공 이론 1+α/2", "#1769aa", [1 + r.actual_load_factor / 2 for r in rows], True),
        ("체이닝 실패 실측", "#c62828", [r.chaining_unsuccessful for r in rows], False),
        ("체이닝 실패 이론 α", "#c62828", [r.actual_load_factor for r in rows], True),
        ("선형 탐지 성공 실측", "#2e7d32", [r.linear_successful for r in rows], False),
        ("선형 탐지 성공 이론", "#2e7d32", [theory[0] for theory in linear_theories], True),
        ("선형 탐지 실패 실측", "#8e24aa", [r.linear_unsuccessful for r in rows], False),
        ("선형 탐지 실패 이론", "#8e24aa", [theory[1] for theory in linear_theories], True),
    )
    pieces = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<text x="490" y="27" text-anchor="middle" font-size="18">체이닝과 선형 탐지 탐색 비용 비교</text>',
    ]
    y_step = max(1, ceil(y_max / 10))
    for tick in range(0, y_max + 1, y_step):
        y = top + plot_height - tick / y_max * plot_height
        pieces.append(f'<path d="M {left} {y:.1f} H {left + plot_width}" stroke="#ddd"/>')
        pieces.append(
            f'<text x="{left - 12}" y="{y + 4:.1f}" text-anchor="end" font-size="12">{tick}</text>'
        )
    for tick in range(10):
        load = tick / 10
        x = left + load / 0.9 * plot_width
        pieces.append(f'<path d="M {x:.1f} {top} V {top + plot_height}" stroke="#eee"/>')
        pieces.append(
            f'<text x="{x:.1f}" y="{top + plot_height + 20}" text-anchor="middle" font-size="12">{load:.1f}</text>'
        )
    pieces.extend(
        [
            f'<path d="M {left} {top} V {top + plot_height} H {left + plot_width}" fill="none" stroke="#333"/>',
            f'<text x="{left + plot_width / 2}" y="{top + plot_height + 44}" text-anchor="middle" font-size="14">적재율 α</text>',
            f'<text x="20" y="{top + plot_height / 2}" text-anchor="middle" font-size="14" transform="rotate(-90 20 {top + plot_height / 2})">평균 탐지 횟수</text>',
        ]
    )
    for index, (label, color, values, dashed) in enumerate(series):
        coordinates = " ".join(
            f"{x:.1f},{y:.1f}"
            for x, y in (
                point(row.actual_load_factor, value)
                for row, value in zip(rows, values)
            )
        )
        dash = ' stroke-dasharray="6 4"' if dashed else ""
        pieces.append(
            f'<polyline points="{coordinates}" fill="none" stroke="{color}" stroke-width="2"{dash}/>'
        )
        legend_x = left + (index % 2) * 410
        legend_y = top + plot_height + 76 + (index // 2) * 25
        pieces.append(
            f'<path d="M {legend_x} {legend_y - 4} h 24" stroke="{color}" stroke-width="2"{dash}/>'
        )
        pieces.append(
            f'<text x="{legend_x + 32}" y="{legend_y}" font-size="12">{label}</text>'
        )
    pieces.append(
        f'<text x="{left}" y="{height - 12}" font-size="11">버킷 {CAPACITY}개 · 적재율당 같은 URL {TRIALS}회 · 시드 {SEED} · 체이닝/선형 탐지 동시 측정</text>'
    )
    pieces.append("</svg>")
    SVG_PATH.write_text("\n".join(pieces), encoding="utf-8")


def main() -> None:
    rows = measure_load_factors()
    write_csv(rows)
    write_svg(rows)

    print("목표 α 실제 α  항목 수  체이닝 성공/실패  선형 탐지 성공/실패")
    for row in rows:
        print(
            f"{row.target_load_factor:>5.2f} {row.actual_load_factor:>6.3f}"
            f" {row.item_count:>7}  {row.chaining_successful:>6.2f}/{row.chaining_unsuccessful:>6.2f}"
            f"  {row.linear_successful:>6.2f}/{row.linear_unsuccessful:>6.2f}"
        )
    print(f"Wrote {CSV_PATH.name} and {SVG_PATH.name}")


if __name__ == "__main__":
    main()
