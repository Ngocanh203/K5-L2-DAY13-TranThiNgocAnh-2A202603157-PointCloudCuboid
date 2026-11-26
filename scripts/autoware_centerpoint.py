"""Run the Autoware CenterPoint v3.0 base ONNX models on an XYZI LiDAR frame."""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path


class CenterPoint:
    # The v3.0 base model manifest fixes the geometry and class order.
    LABELS = ("car", "truck", "bus", "bicycle", "pedestrian")
    GRID = 480
    ORIGIN = -76.8
    CELL = 0.32
    Z_MIN, Z_MAX = -4.0, 6.0
    POINTS_PER_PILLAR = 32
    MAX_PILLARS = 40000
    MIN_SCORE = 0.35

    def __init__(self, assets, runtime):
        if runtime:
            sys.path.insert(0, str(runtime.resolve()))
        try:
            import numpy as np
            import onnxruntime as ort
        except ImportError as exc:
            raise ValueError("CenterPoint CPU needs NumPy and ONNX Runtime in the configured runtime.") from exc
        self.np = np
        options = ort.SessionOptions()
        options.intra_op_num_threads = 4
        providers = ["CPUExecutionProvider"]
        self.encoder = ort.InferenceSession(str(assets / "pts_voxel_encoder_centerpoint.onnx"),
                                            options, providers=providers)
        self.detector = ort.InferenceSession(str(assets / "pts_backbone_neck_head_centerpoint.onnx"),
                                             options, providers=providers)

    def encode_frame(self, path):
        np = self.np
        points = np.fromfile(path, dtype="<f4").reshape(-1, 4)
        # VF (left, back, up) to ROS LiDAR (forward, left, up).
        xyz = points[:, [1, 0, 2]].copy()
        xyz[:, 0] *= -1
        edge = self.ORIGIN + self.GRID * self.CELL
        valid = np.isfinite(xyz).all(axis=1)
        valid &= ((xyz[:, :2] >= self.ORIGIN) & (xyz[:, :2] < edge)).all(axis=1)
        valid &= (xyz[:, 2] >= self.Z_MIN) & (xyz[:, 2] < self.Z_MAX)
        xyz = xyz[valid]
        if not len(xyz):
            return None
        coords = np.floor((xyz[:, :2] - self.ORIGIN) / self.CELL).astype(np.int32)
        in_grid = ((coords >= 0) & (coords < self.GRID)).all(axis=1)
        coords, xyz = coords[in_grid], xyz[in_grid]
        if not len(xyz):
            return None

        keys = coords[:, 1] * self.GRID + coords[:, 0]
        order = np.argsort(keys, kind="stable")
        cells, starts, counts = np.unique(keys[order], return_index=True, return_counts=True)
        pillar = np.repeat(np.arange(len(cells)), counts)
        slot = np.arange(len(order)) - np.repeat(starts, counts)
        kept = (pillar < self.MAX_PILLARS) & (slot < self.POINTS_PER_PILLAR)
        pillar, slot, xyz = pillar[kept], slot[kept], xyz[order[kept]]
        cells = cells[:self.MAX_PILLARS]
        gx, gy = cells % self.GRID, cells // self.GRID
        sums = np.zeros((len(cells), 3), dtype=np.float32)
        np.add.at(sums, pillar, xyz)
        means = sums / np.minimum(counts[:len(cells)], self.POINTS_PER_PILLAR)[:, None]
        centers = self.ORIGIN + (np.column_stack((gx, gy)) + 0.5) * self.CELL
        # Per point: xyz, single-sweep time lag (0), xyz offset from mean, xy offset from cell center.
        features = np.zeros((len(cells), self.POINTS_PER_PILLAR, 9), dtype=np.float32)
        features[pillar, slot, :3] = xyz
        features[pillar, slot, 4:7] = xyz - means[pillar]
        features[pillar, slot, 7:9] = xyz[:, :2] - centers[pillar]

        encoded, = self.encoder.run(["pillar_features"], {"input_features": features})
        grid = np.zeros((1, 32, self.GRID, self.GRID), dtype=np.float32)
        grid[0][:, gy, gx] = encoded[:, 0, :].T
        return grid

    def predict(self, path):
        np = self.np
        grid = self.encode_frame(path)
        if grid is None:
            return []
        heatmap, offsets, heights, sizes, rotations = [
            tensor[0] for tensor in self.detector.run(
                ["heatmap", "reg", "height", "dim", "rot"], {"spatial_features": grid},
            )
        ]
        labels = heatmap.argmax(axis=0)
        logits = heatmap.max(axis=0)
        threshold = math.log(self.MIN_SCORE / (1 - self.MIN_SCORE))
        rows, columns = np.nonzero(logits >= threshold)
        x = self.ORIGIN + (columns + offsets[0, rows, columns]) * self.CELL
        y = self.ORIGIN + (rows + offsets[1, rows, columns]) * self.CELL
        inside = np.hypot(x, y) <= 50
        rows, columns, x, y = rows[inside], columns[inside], x[inside], y[inside]

        predictions = []
        centers = []
        order = np.argsort(-logits[rows, columns], kind="stable")
        for index in order:
            px, py = float(x[index]), float(y[index])
            if any((px - cx) ** 2 + (py - cy) ** 2 < 0.5 ** 2 for cx, cy in centers):
                continue
            row, col = rows[index], columns[index]
            width, length, height = map(float, np.exp(sizes[:, row, col]))
            sine, cosine = map(float, rotations[:, row, col])
            # Autoware's native head yaw is converted to the ROS heading before VF conversion.
            yaw = -math.atan2(sine, cosine) - math.pi / 2
            box = [px, py, float(heights[0, row, col]), length, width, height, yaw]
            if all(math.isfinite(value) for value in box) and min(width, length, height) > 0:
                score = 1 / (1 + math.exp(-float(logits[row, col])))
                predictions.append({"label": self.LABELS[int(labels[row, col])], "score": score, "box": box})
                centers.append((px, py))
        return predictions


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frame-manifest", type=Path, required=True)
    parser.add_argument("--models", type=Path, required=True)
    parser.add_argument("--runtime", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    paths = json.loads(args.frame_manifest.read_text(encoding="utf-8"))
    model = CenterPoint(args.models, args.runtime)
    predictions = {}
    for frame, path in paths.items():
        predictions[frame] = model.predict(Path(path))
        print(f"{frame}: {len(predictions[frame])} candidates", flush=True)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(predictions, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
