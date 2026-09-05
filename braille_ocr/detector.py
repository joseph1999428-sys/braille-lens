"""OpenCV based six-dot Braille image detector.

The detector is deliberately geometry-first. It does not assume a particular
font or a fixed image resolution: connected components provide dot centers,
then the centers are clustered into row and cell grids. This works well for
clean scans and high-resolution photographs, while exposing diagnostics when a
page needs better lighting or a threshold adjustment.
"""

from __future__ import annotations

from collections.abc import Iterable
from io import BytesIO
from math import pi, sqrt

import cv2
import numpy as np
from PIL import Image

from .models import Cell, Dot, OCRConfig, OCRResult
from .translator import decode_cells


def _to_rgb_array(image: Image.Image | np.ndarray | bytes) -> np.ndarray:
    if isinstance(image, bytes):
        image = Image.open(BytesIO(image))
    if isinstance(image, Image.Image):
        return np.asarray(image.convert("RGB"))
    array = np.asarray(image)
    if array.ndim == 2:
        return cv2.cvtColor(array.astype(np.uint8), cv2.COLOR_GRAY2RGB)
    if array.shape[2] == 4:
        return cv2.cvtColor(array.astype(np.uint8), cv2.COLOR_RGBA2RGB)
    return array.astype(np.uint8)


def _binary_mask(rgb: np.ndarray, config: OCRConfig) -> tuple[np.ndarray, float]:
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    # A small blur suppresses JPEG grain without erasing raised-dot edges.
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    if config.threshold_mode == "adaptive":
        block = max(3, int(config.adaptive_block_size) | 1)
        binary = cv2.adaptiveThreshold(
            gray,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV,
            block,
            config.adaptive_c,
        )
        threshold_value = float(np.mean(gray))
    elif config.threshold_mode == "local_contrast":
        # Faint embossed dots in a page photo may be only a few gray levels
        # darker than the paper. A blurred background subtraction removes the
        # page illumination gradient before thresholding those dots.
        background = cv2.GaussianBlur(gray, (0, 0), 12)
        contrast = cv2.subtract(background, gray)
        threshold_value, binary = cv2.threshold(
            contrast, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
        )
        threshold_value = float(threshold_value)
    else:
        threshold_value, binary = cv2.threshold(
            gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
        )
    if config.invert:
        binary = cv2.bitwise_not(binary)

    # Opening removes isolated sensor noise. Closing repairs small holes in
    # the dark center of an embossed dot.
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
    return binary, threshold_value


def _cluster(values: Iterable[float], tolerance: float) -> list[float]:
    sorted_values = sorted(float(value) for value in values)
    if not sorted_values:
        return []
    groups: list[list[float]] = [[sorted_values[0]]]
    for value in sorted_values[1:]:
        if value - float(np.mean(groups[-1])) <= tolerance:
            groups[-1].append(value)
        else:
            groups.append([value])
    return [float(np.mean(group)) for group in groups]


def _estimate_pitch(gaps: np.ndarray, fallback: float) -> float:
    gaps = np.asarray(gaps, dtype=float)
    gaps = gaps[np.isfinite(gaps) & (gaps > 0.5)]
    if not len(gaps):
        return float(fallback)
    # The shortest repeated spacing is the two-column dot pitch. When a line
    # contains mostly one-column characters there may be only one such gap, so
    # use a plausible dot-sized neighborhood around the fallback as well.
    near = gaps[gaps <= float(fallback) * 1.55]
    search = near if len(near) else gaps
    for candidate in np.sort(search):
        cluster = gaps[np.abs(gaps - candidate) <= max(2.0, candidate * 0.14)]
        if len(cluster) >= 2:
            return float(np.median(cluster))
    return float(np.median(search))


def _modal_pitch(gaps: np.ndarray, fallback: float) -> float:
    """Estimate the repeated grid spacing, tolerating unrelated handwriting.

    Full-page photos often contain a few small gaps from printed labels or
    compression artifacts. Braille row spacing is the spacing that repeats most
    often, so a mode-like cluster is safer here than the shortest gap.
    """

    values = np.asarray(gaps, dtype=float)
    values = values[np.isfinite(values) & (values > 0.5)]
    if not len(values):
        return float(fallback)
    clusters: list[list[float]] = []
    for value in sorted(values):
        if not clusters or value - float(np.mean(clusters[-1])) > max(2.0, value * 0.12):
            clusters.append([float(value)])
        else:
            clusters[-1].append(float(value))
    best = max(clusters, key=lambda group: (len(group), float(np.mean(group))))
    return float(np.median(best))


def _row_layout(dots: list[Dot], radius: float) -> tuple[list[list[Dot]], list[list[float]], float]:
    row_tolerance = max(2.0, radius * 1.35)
    row_centers = _cluster((dot.y for dot in dots), row_tolerance)
    if not row_centers:
        return [], [], max(radius * 2.0, 1.0)
    gaps = np.diff(row_centers)
    # Dot rows are wider than a dot itself but much smaller than the gap
    # between lines. This excludes the small gaps made by handwriting above a
    # Braille block while retaining low-resolution photographs.
    row_candidates = gaps[(gaps >= radius * 2.5) & (gaps <= radius * 8.0)]
    dy = _modal_pitch(row_candidates if len(row_candidates) else gaps, max(radius * 3.0, 1.0))
    # Split row-center runs at the larger gap between Braille text lines. A
    # handwritten heading can create several extra centers inside one run, so
    # each run is reduced to the best-fitting three-row Braille pattern.
    line_break = max(dy * 1.8, dy + radius * 2.0)
    runs: list[list[float]] = [[row_centers[0]]]
    for center, gap in zip(row_centers[1:], gaps):
        if gap > line_break:
            runs.append([center])
        else:
            runs[-1].append(center)

    def row_support(center: float) -> int:
        return sum(abs(dot.y - center) <= max(2.5, dy * 0.42) for dot in dots)

    line_centers: list[list[float]] = []
    for run in runs:
        if len(dots) > 100 and len(run) < 3:
            continue
        if len(run) <= 3:
            selected = run
        else:
            candidates: list[tuple[float, list[float]]] = []
            for start in range(len(run) - 2):
                triple = run[start : start + 3]
                spacing_error = sum(abs((triple[i + 1] - triple[i]) - dy) for i in range(2))
                support = sum(row_support(center) for center in triple)
                candidates.append((support - spacing_error * 1.5, triple))
            selected = max(candidates, key=lambda item: item[0])[1]
        if sum(row_support(center) for center in selected) >= max(2, int(len(dots) * 0.006)):
            line_centers.append(selected)

    line_dots: list[list[Dot]] = [[] for _ in line_centers]
    for dot in dots:
        nearest_line = None
        nearest_distance = float("inf")
        for line_index, centers in enumerate(line_centers):
            distance = min(abs(dot.y - center) for center in centers)
            if distance < nearest_distance:
                nearest_line, nearest_distance = line_index, distance
        if nearest_line is not None and nearest_distance <= max(4.0, dy * 0.55):
            line_dots[nearest_line].append(dot)
    return line_dots, line_centers, dy


def _line_cells(
    dots: list[Dot],
    row_centers: list[float],
    line_index: int,
    config: OCRConfig,
    radius: float,
    grid_pitch: float | None = None,
) -> tuple[list[Cell], float]:
    if not dots or not row_centers:
        return [], max(radius * 2.0, 1.0)

    x_columns = _cluster((dot.x for dot in dots), max(1.5, radius * 0.55))
    x_gaps = np.diff(x_columns)
    dx = _estimate_pitch(x_gaps, grid_pitch or max(radius * 2.8, 1.0))
    column_tolerance = max(2.0, dx * 0.32)
    x_columns = _cluster((dot.x for dot in dots), column_tolerance)
    x_gaps = np.diff(x_columns)
    if grid_pitch is not None:
        # The six-dot horizontal pitch is close to the row pitch. Using the
        # page-wide estimate keeps one-column cells (I, punctuation, capitals)
        # aligned when a particular line has too few dots to infer it alone.
        dx = float(grid_pitch)
    else:
        dx = _estimate_pitch(x_gaps, dx)

    # A gap within a cell is approximately one dx. The next cell starts after
    # a larger gap, so this ratio separates cells even when a dot is missing.
    groups: list[list[float]] = [[x_columns[0]]]
    for x, gap in zip(x_columns[1:], np.diff(x_columns)):
        if gap <= config.cell_gap_ratio * dx:
            groups[-1].append(x)
        else:
            groups.append([x])

    # Prevent an unusually noisy line from producing a three-column cell.
    normalized_groups: list[list[float]] = []
    for group in groups:
        if len(group) <= 2:
            normalized_groups.append(group)
            continue
        for offset in range(0, len(group), 2):
            normalized_groups.append(group[offset : offset + 2])
    groups = normalized_groups

    two_column_lefts = [group[0] for group in groups if len(group) == 2]
    # Looking only at complete cells misses the pitch when neighboring cells
    # contain one column each. Use all occupied group anchors and select the
    # smallest repeated gap that is clearly wider than a within-cell column.
    anchor_gaps = np.diff([group[0] for group in groups])
    cell_gap_candidates = anchor_gaps[
        (anchor_gaps >= dx * 1.9) & (anchor_gaps <= dx * 3.6)
    ]
    cell_pitch = _estimate_pitch(cell_gap_candidates, dx * 2.7)
    if cell_pitch <= dx:
        cell_pitch = dx * 2.7
    cell_pitch = max(cell_pitch, dx * 1.7)
    # Preserve the phase of an actual left-column center. Taking the median of
    # an even number of columns can land halfway between the 76 px lattice
    # positions and misclassify an isolated right-column capital indicator.
    left_reference = float(two_column_lefts[0]) if two_column_lefts else float(groups[0][0])

    cells: list[Cell] = []
    anchors: list[float] = []
    for group in groups:
        if not group:
            continue
        right_only = False
        if len(group) == 2:
            columns = group
            anchor = group[0]
        else:
            x = group[0]
            # Locate the nearest expected left-column phase. This lets a cell
            # containing only right-column dots retain its column identity.
            phase = round((x - left_reference) / cell_pitch)
            expected_left = left_reference + phase * cell_pitch
            if abs(x - expected_left) <= abs(x - (expected_left + dx)):
                columns = [x]
                right_only = False
                anchor = x
            else:
                columns = [x]
                right_only = True
                anchor = x - dx

        group_dots = [dot for dot in dots if min(abs(dot.x - value) for value in group) <= column_tolerance * 1.8]
        mask = 0
        row_hits = 0
        for dot in group_dots:
            row_index = int(np.argmin([abs(dot.y - center) for center in row_centers]))
            if abs(dot.y - row_centers[row_index]) > max(4.0, radius * 1.8):
                continue
            if row_index >= 3:
                continue
            if len(columns) == 2:
                column_index = 0 if abs(dot.x - columns[0]) <= abs(dot.x - columns[1]) else 1
            else:
                column_index = 1 if "right_only" in locals() and right_only else 0
            dot_number = row_index + 1 + (3 if column_index else 0)
            mask |= 1 << (dot_number - 1)
            row_hits += 1
        if not group_dots:
            continue
        confidence = min(1.0, 0.55 + 0.18 * row_hits)
        cells.append(
            Cell(
                mask=mask,
                x=float(np.mean(group)),
                y=float(np.mean(row_centers[:3])),
                line_index=line_index,
                confidence=confidence,
                dot_count=row_hits,
            )
        )
        anchors.append(anchor)

    # Add inferred blank cells for word-sized gaps. A blank is represented in
    # the same stream as an ordinary cell and is later rendered as a space.
    with_spaces: list[Cell] = []
    for index, cell in enumerate(cells):
        with_spaces.append(cell)
        if index >= len(cells) - 1:
            continue
        current_anchor = anchors[index]
        next_anchor = anchors[index + 1]
        distance = next_anchor - current_anchor
        missing = max(0, int(round(distance / cell_pitch)) - 1)
        if distance > cell_pitch * 1.45 and missing:
            for blank_index in range(missing):
                with_spaces.append(
                    Cell(
                        mask=0,
                        x=current_anchor + cell_pitch * (blank_index + 1),
                        y=cell.y,
                        line_index=line_index,
                        confidence=0.85,
                        is_space=True,
                    )
                )
    order = np.argsort([cell.x for cell in with_spaces])
    return [with_spaces[int(index)] for index in order], cell_pitch


def detect_braille(
    image: Image.Image | np.ndarray | bytes,
    config: OCRConfig | None = None,
    grade: str = "Grade 1",
) -> OCRResult:
    """Detect Braille dots in ``image`` and translate them to English."""

    config = config or OCRConfig()
    mode_used = config.threshold_mode
    rgb = _to_rgb_array(image)
    binary, threshold = _binary_mask(rgb, config)
    component_count, labels, stats, centroids = cv2.connectedComponentsWithStats(
        binary, connectivity=8
    )
    raw_areas = stats[1:, cv2.CC_STAT_AREA].astype(float)
    valid_areas = raw_areas[
        (raw_areas >= config.min_component_area)
        & (raw_areas <= config.max_component_area)
    ]
    # On a full-page, low-contrast photo the local-contrast mask is much more
    # reliable than a global threshold. Retry automatically when the global
    # pass produces an implausibly dense collection of tiny components.
    if config.threshold_mode == "otsu" and (
        len(valid_areas) > 350 or (len(valid_areas) and float(np.median(valid_areas)) < 20)
    ):
        local_config = OCRConfig(
            threshold_mode="adaptive",
            invert=config.invert,
            min_component_area=max(2, config.min_component_area // 2),
            max_component_area=config.max_component_area,
            adaptive_block_size=config.adaptive_block_size,
            adaptive_c=config.adaptive_c,
            dot_row_tolerance=config.dot_row_tolerance,
            cell_gap_ratio=config.cell_gap_ratio,
        )
        binary, threshold = _binary_mask(rgb, local_config)
        mode_used = "adaptive (automatic fallback)"
        component_count, labels, stats, centroids = cv2.connectedComponentsWithStats(
            binary, connectivity=8
        )
        raw_areas = stats[1:, cv2.CC_STAT_AREA].astype(float)
        valid_areas = raw_areas[
            (raw_areas >= local_config.min_component_area)
            & (raw_areas <= local_config.max_component_area)
        ]
    if not len(valid_areas):
        return OCRResult(
            text="",
            binary=binary,
            annotated=Image.fromarray(rgb),
            confidence=0.0,
            diagnostics={
                "threshold": threshold,
                "image_size": f"{rgb.shape[1]} x {rgb.shape[0]}",
                "components": int(component_count - 1),
                "dots": 0,
                "message": "No dot-sized connected components were found.",
            },
        )

    median_area = float(np.median(valid_areas))
    lower = max(float(config.min_component_area), median_area * 0.18)
    upper = min(float(config.max_component_area), median_area * 4.5)
    dots: list[Dot] = []
    for index in range(1, component_count):
        area = float(stats[index, cv2.CC_STAT_AREA])
        if not lower <= area <= upper:
            continue
        width = float(stats[index, cv2.CC_STAT_WIDTH])
        height = float(stats[index, cv2.CC_STAT_HEIGHT])
        fill = area / max(width * height, 1.0)
        if fill < 0.20:
            continue
        # Pen strokes and page scratches are usually much longer in one
        # direction than a Braille dot. Keep mildly elongated components for
        # touching-dot photographs, but reject obvious line fragments.
        aspect = max(width / max(height, 1.0), height / max(width, 1.0))
        if aspect > 3.2:
            continue
        radius = sqrt(area / pi)
        score = min(1.0, fill / 0.78) * min(1.0, area / max(median_area, 1.0))
        dots.append(
            Dot(
                x=float(centroids[index][0]),
                y=float(centroids[index][1]),
                area=area,
                radius=radius,
                score=float(max(0.0, min(1.0, score))),
            )
        )

    if not dots:
        return OCRResult(
            text="",
            binary=binary,
            annotated=Image.fromarray(rgb),
            confidence=0.0,
            diagnostics={
                "threshold": threshold,
                "image_size": f"{rgb.shape[1]} x {rgb.shape[0]}",
                "components": int(component_count - 1),
                "dots": 0,
                "message": "Components were found, but none matched the dot shape and size filter.",
            },
        )

    radius = float(np.median([dot.radius for dot in dots]))
    line_dots, line_rows, dy = _row_layout(dots, radius)
    page_dx_values: list[float] = []
    for dots_on_line in line_dots:
        if len(dots_on_line) < 8:
            continue
        columns = _cluster((dot.x for dot in dots_on_line), max(1.5, radius * 0.55))
        if len(columns) > 1:
            page_dx_values.append(_estimate_pitch(np.diff(columns), dy))
    page_dx = float(np.median(page_dx_values)) if page_dx_values else None
    cells: list[Cell] = []
    cell_pitch = 0.0
    for line_index, (dots_on_line, row_centers) in enumerate(zip(line_dots, line_rows)):
        line_cells, pitch = _line_cells(dots_on_line, row_centers, line_index, config, radius, page_dx)
        cells.extend(line_cells)
        cell_pitch = pitch if pitch else cell_pitch

    text, translation_confidence = decode_cells(cells, grade=grade)
    geometry_confidence = float(np.mean([dot.score for dot in dots])) if dots else 0.0
    confidence = float(max(0.0, min(1.0, 0.55 * geometry_confidence + 0.45 * translation_confidence)))

    annotated_bgr = cv2.cvtColor(rgb.copy(), cv2.COLOR_RGB2BGR)
    for dot in dots:
        cv2.circle(annotated_bgr, (round(dot.x), round(dot.y)), max(2, round(dot.radius)), (50, 205, 50), 2)
    for index, cell in enumerate(cells):
        if cell.is_space:
            continue
        x = int(round(cell.x))
        y = int(round(cell.y))
        cv2.putText(
            annotated_bgr,
            str(index + 1),
            (x, max(14, y - 10)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.42,
            (210, 80, 30),
            1,
            cv2.LINE_AA,
        )
    annotated = Image.fromarray(cv2.cvtColor(annotated_bgr, cv2.COLOR_BGR2RGB))
    diagnostics = {
        "threshold_mode": mode_used,
        "threshold": round(float(threshold), 2),
        "image_size": f"{rgb.shape[1]} x {rgb.shape[0]}",
        "components": int(component_count - 1),
        "dots": len(dots),
        "cells": len(cells),
        "lines": len(line_rows),
        "row_pitch_px": round(float(dy), 2),
        "column_pitch_px": round(float(cell_pitch), 2),
        "median_dot_area_px": round(median_area, 2),
        "recognized_ratio": round(float(translation_confidence), 3),
    }
    return OCRResult(
        text=text,
        cells=cells,
        dots=dots,
        binary=binary,
        annotated=annotated,
        confidence=confidence,
        diagnostics=diagnostics,
    )
