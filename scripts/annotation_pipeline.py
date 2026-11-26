"""Pre-label and check cuboids in CVAT 3D."""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cvat_lab"))
import vf_common as vf
import vf_qa as qa

LABELS = {name.lower(): name for name in vf.CLASS_IDS}
LABELS.update(trailer="Truck", construction_vehicle="Truck",
              motorcycle="Cyclist", bicycle="Cyclist")
CYCLIST_CANDIDATES = {"motorcycle", "bicycle"}
GEOMETRY = ("x", "y", "z", "length", "width", "height", "yaw")
MANUAL_REVIEW = (
    "Quét đủ 360°, ưu tiên vật rõ trong 30 m. Tìm hộp bị sót hoặc điểm lạ; bỏ qua xe thu dữ liệu.",
    "Kiểm lớp bằng camera. Van chở người là Car, minibus chở khách là Bus, bán tải và van chở hàng là Truck. "
    "Đầu kéo và rơ-moóc dùng hai hộp Truck. "
    "Xe hai bánh có người ngồi là Cyclist (bao người và xe); người dắt xe là Pedestrian; bỏ qua xe không người.",
    "Kiểm đủ sáu mặt trên Top, Side, Front. Bao trọn vật, cả phần nhô ra và phần bị che có cơ sở suy ra. "
    "So với kích thước thực tế: Car/Bus/Truck ±5%, Pedestrian/Cyclist ±10%.",
    "Kiểm đầu xe hoặc hướng di chuyển bằng camera. Với người đứng yên, căn theo hướng mặt.",
    "Bật Occluded khi vật bị che một phần. Với vật chỉ thấy dưới khoảng 15–20% thể tích, "
    "chỉ vẽ khi đủ cơ sở suy ra hình dạng. Nếu còn nghi vấn, ghi frame, vị trí và loại nghi vấn "
    "(UNCERTAIN_CLASS, UNCERTAIN_SCOPE, ATTRIBUTE_CHECK hoặc LOW_VISIBILITY) vào báo cáo.",
)


def scan_files(folder):
    paths = {path.stem: path for path in sorted(folder.glob("*.bin")) if path.is_file()}
    if not paths:
        raise ValueError(f"No .bin frames in {folder}")
    return paths


def model_predictions(paths, config, checkpoint, device):
    try:
        import numpy as np
        from mmdet3d.apis import inference_detector, init_model
    except ImportError as exc:
        raise ValueError("Run prelabel in an MMDetection3D environment (see docs/PRELABEL.md).") from exc

    model = init_model(str(config), str(checkpoint), device=device)
    dataset = model.cfg.test_dataloader.dataset
    dataset.pipeline = [step for step in dataset.pipeline
                        if step.type != "LoadPointsFromMultiSweeps"]
    if (dataset.pipeline[0].type != "LoadPointsFromFile"
            or dataset.pipeline[0].load_dim != 5 or dataset.pipeline[0].use_dim != 5):
        raise ValueError("Use a CenterPoint nuScenes config with a five-feature point loader.")
    classes = model.dataset_meta["classes"]
    for frame, path in paths.items():
        vf_points = np.asarray(vf.read_bin(path), dtype=np.float32).reshape(-1, 4)
        if not len(vf_points) or not np.isfinite(vf_points).all():
            raise ValueError(f"{frame}: point cloud is empty or has non-finite values")
        points = np.zeros((len(vf_points), 5), dtype=np.float32)
        points[:, 0] = -vf_points[:, 1]
        points[:, 1] = vf_points[:, 0]
        points[:, 2:4] = vf_points[:, 2:4]
        sample, _ = inference_detector(model, points)
        pred = sample.pred_instances_3d
        boxes = pred.bboxes_3d
        centers = boxes.gravity_center.cpu().tolist()
        dims = boxes.dims.cpu().tolist()
        yaws = boxes.yaw.cpu().tolist()
        scores = pred.scores_3d.cpu().tolist()
        labels = pred.labels_3d.cpu().tolist()
        yield frame, [
            {"label": classes[label], "score": score, "box": center + size + [yaw]}
            for center, size, yaw, score, label in zip(centers, dims, yaws, scores, labels, strict=True)
        ]


def map_predictions(predictions, score_min, max_range):
    boxes = []
    for prediction in predictions:
        source = prediction["label"].lower()
        score = float(prediction["score"])
        if not math.isfinite(score) or not 0 <= score <= 1:
            raise ValueError("A prediction score is outside [0, 1].")
        if source not in LABELS or score < score_min:
            continue
        x, y, z, length, width, height, yaw = map(float, prediction["box"])
        if not all(math.isfinite(v) for v in (x, y, z, length, width, height, yaw)):
            raise ValueError("A prediction contains non-finite geometry.")
        if min(length, width, height) <= 0:
            raise ValueError("A prediction has a non-positive dimension.")
        if math.hypot(x, y) <= max_range:
            values = (y, -x, z, length, width, height, vf.wrap_yaw(yaw - math.pi / 2))
            boxes.append({**dict(zip(GEOMETRY, values, strict=True)), "idx": len(boxes) + 1,
                          "label": LABELS[source], "source_label": source, "score": score,
                          "confirm_rider": source in CYCLIST_CANDIDATES})
    return boxes


def cvat_client():
    from cvat_sdk import make_client

    token = os.environ.get("CVAT_ACCESS_TOKEN", "").strip()
    env_file = ROOT / ".env"
    if not token and env_file.is_file():
        for line in env_file.read_text(encoding="utf-8-sig").splitlines():
            key, _, value = line.partition("=")
            if key.strip() == "CVAT_ACCESS_TOKEN":
                token = value.strip().strip('"').strip("'")
                break
    if not token:
        raise ValueError("Set CVAT_ACCESS_TOKEN for the local CVAT connection.")
    return make_client("http://localhost:8080", access_token=token)


def job_frames(job, task):
    if task.dimension != "3d":
        raise ValueError("The CVAT job must belong to a 3D task.")
    meta = task.get_meta()
    indices = {
        Path(meta.frames[index - meta.start_frame].name).stem: index
        for index in range(job.start_frame, job.stop_frame + 1)
    }
    if len(indices) != job.stop_frame - job.start_frame + 1:
        raise ValueError("CVAT job has duplicate frame names.")
    return indices


def seed_job(job_id, frames):
    from cvat_sdk import models
    from cvat_sdk.core.proxies.annotations import AnnotationUpdateAction

    with cvat_client() as client:
        job = client.jobs.retrieve(job_id)
        task = client.tasks.retrieve(job.task_id)
        indices = job_frames(job, task)
        if indices.keys() != frames.keys():
            raise ValueError("The .bin stems must match the CVAT job frame names exactly.")
        labels = {label.name: label.id for label in task.get_labels()}
        if not vf.CLASS_IDS.keys() <= labels.keys():
            raise ValueError("The CVAT task must define all five lab labels.")
        annotations = job.get_annotations()
        occupied = {index: [] for index in indices.values()}
        for shape in annotations.shapes:
            if (str(getattr(shape.type, "value", shape.type)) == "cuboid"
                    and not getattr(shape, "outside", False) and shape.frame in occupied):
                occupied[shape.frame].append(vf.cuboid_from_cvat(shape.points, ""))
        shapes, duplicates = [], 0
        for frame, boxes in frames.items():
            index = indices[frame]
            for box in sorted(boxes, key=lambda candidate: candidate["score"], reverse=True):
                if box["confirm_rider"]:
                    continue
                if any(same_object_candidate(box, saved) for saved in occupied[index]):
                    duplicates += 1
                    continue
                shapes.append(models.LabeledShapeRequest(
                    type="cuboid", frame=index, label_id=labels[box["label"]],
                    # CVAT uses 16 numbers. Its 3D canvas packs center, rotation, scale and seven zeros.
                    points=[box["x"], box["y"], box["z"], 0.0, 0.0, box["yaw"],
                            box["length"], box["width"], box["height"], *([0.0] * 7)],
                    source="auto", score=box["score"],
                ))
                occupied[index].append(box)
        if shapes:
            data = models.PatchedLabeledDataRequest(version=annotations.version, shapes=shapes)
            job.update_annotations(data, action=AnnotationUpdateAction.CREATE)
        return len(shapes), duplicates


def same_object_candidate(left, right):
    vertical_overlap = abs(left["z"] - right["z"]) < (left["height"] + right["height"]) / 2
    return vertical_overlap and vf.bev_iou(left, right) >= 0.30


def read_job(job_id):
    with cvat_client() as client:
        job = client.jobs.retrieve(job_id)
        task = client.tasks.retrieve(job.task_id)
        indices = job_frames(job, task)
        frames, issues = read_annotations(job, task, indices)
        return frames, issues, lab_minimums(task.name, indices)


def read_annotations(job, task, indices):
    names = {index: name for name, index in indices.items()}
    labels = {label.id: label.name for label in task.get_labels()}
    frames = {name: [] for name in indices}
    annotations = job.get_annotations()
    for shape in annotations.shapes:
        if str(getattr(shape.type, "value", shape.type)) != "cuboid":
            continue
        box = vf.cuboid_from_cvat(shape.points, labels[shape.label_id], occluded=shape.occluded)
        frames[names[shape.frame]].append({
            **box, "idx": shape.id, "object_type": "shape",
            "roll": float(shape.points[3]), "pitch": float(shape.points[4]),
            "outside": getattr(shape, "outside", False),
            "score": getattr(shape, "score", None) if getattr(shape, "source", None) == "auto" else None,
        })
    issues = [
        {
            "frame": names[track.frame], "idx": track.id, "label": labels[track.label_id],
            "object_type": "track", "flags": "Lab Day 13 yêu cầu Shape riêng từng frame. Hãy kiểm lại Track này.",
        }
        for track in annotations.tracks
        if track.frame in names
        and any(str(getattr(shape.type, "value", shape.type)) == "cuboid" for shape in track.shapes)
    ]
    return frames, issues


def lab_minimums(task_name, indices):
    if not task_name.startswith("D13-") or len(indices) != 10:
        return {}
    from lab import load_config

    config = load_config(require_student=False)
    if not config.get("student") or task_name != vf.task_name(config["student"]):
        return {}
    ordered = sorted(indices, key=indices.get)
    return {frame: 8 if index == 0 else 5 for index, frame in enumerate(ordered)}


def dimension_reference():
    guideline = (ROOT / "docs" / "GUIDELINE.md").read_text(encoding="utf-8")
    table = guideline.split("## 3.", 1)[1].split("## 4.", 1)[0]
    ranges = {label: [] for label in vf.CLASS_IDS}
    for line in table.splitlines():
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) == 5 and cells[1] in ranges:
            ranges[cells[1]].append(tuple(
                tuple(float(value.strip().replace(",", ".")) for value in cell.split("–"))
                for cell in cells[2:]
            ))
    if not all(ranges.values()):
        raise ValueError("Bảng 4.3 của guideline thiếu khoảng kích thước cho một hoặc nhiều lớp.")
    return ranges


def prelabel(args, *, paths=None):
    if paths is None:
        if args.frame_manifest:
            manifest = json.loads(args.frame_manifest.read_text(encoding="utf-8-sig"))
            paths = {frame: Path(path) for frame, path in manifest.items()}
            if not paths or not all(path.is_file() for path in paths.values()):
                raise ValueError("The frame manifest must name existing point cloud files.")
        else:
            paths = scan_files(args.frames)
    if args.predictions:
        raw = json.loads(args.predictions.read_text(encoding="utf-8-sig"))
        if not isinstance(raw, dict) or raw.keys() != paths.keys():
            raise ValueError("Prediction JSON must contain exactly the input .bin frame stems.")
        items = raw.items()
    else:
        if not args.config.is_file() or not (args.checkpoint and args.checkpoint.is_file()):
            raise ValueError("Provide local files for --config and --checkpoint.")
        items = model_predictions(paths, args.config, args.checkpoint, args.device)
    frames = {frame: map_predictions(raw_boxes, args.score_min, args.max_range)
              for frame, raw_boxes in items}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({"frames": frames}, indent=2), encoding="utf-8")
    pending = sum(box["confirm_rider"] for boxes in frames.values() for box in boxes)
    total = sum(map(len, frames.values()))
    print(f"{total} candidates in {len(frames)} frames, {pending} need rider confirmation: {args.out}")
    if args.job is not None:
        added, duplicates = seed_job(args.job, frames)
        print(f"Added {added} Shapes to CVAT job #{args.job}, skipped {duplicates} overlapping candidates.")


def check(args):
    paths = scan_files(args.frames)
    if args.job is not None:
        frames, issues, minimums = read_job(args.job)
    else:
        frames = json.loads(args.input.read_text(encoding="utf-8-sig"))["frames"]
        issues, minimums = [], {}
    rows = review_frames(paths, frames, minimums=minimums,
                         score_review=args.score_review, max_range=args.max_range)
    rows.extend(issues)
    write_review(args.out, rows)
    print(f"{sum(bool(row['flags']) for row in rows)} flagged rows in {args.out}")
    print("Kiểm thủ công theo guideline:")
    for item in MANUAL_REVIEW:
        print(f"- {item}")


def review_frames(paths, frames, *, minimums=None, score_review=0.35, max_range=50.0):
    if paths.keys() != frames.keys():
        raise ValueError("The .bin stems must match the checked frames exactly.")
    rows = []
    minimums = minimums or {}
    dimensions = dimension_reference()
    for frame, path in paths.items():
        boxes = frames[frame]
        count = sum(not box.get("outside", False) for box in boxes)
        minimum = minimums.get(frame)
        if minimum is not None and count < minimum:
            rows.append({"frame": frame, "flags":
                         f"Mới có {count}/{minimum} Shape theo yêu cầu frame. Quét lại cảnh để tìm vật còn sót."})
        elif not boxes:
            rows.append({"frame": frame, "flags": "Frame trống. Quét lại cảnh để tìm vật còn sót."})
        if not boxes:
            continue
        for box, result in zip(boxes, qa.check_frame(boxes, qa.points_xyz(path)), strict=True):
            extra = []
            score = box.get("score")
            if score is not None and score < score_review:
                extra.append("Low model confidence")
            if box.get("confirm_rider"):
                extra.append("Confirm rider before assigning Cyclist")
            if box["label"] not in vf.CLASS_IDS:
                extra.append("Label outside the five lab classes")
            else:
                size = (box["length"], box["width"], box["height"])
                if not any(all(low <= value <= high for value, (low, high) in zip(size, subtype, strict=True))
                           for subtype in dimensions[box["label"]]):
                    extra.append(f"Kích thước {size[0]:.2f} × {size[1]:.2f} × {size[2]:.2f} m "
                                 f"ngoài khoảng tham chiếu Bảng 4.3 cho {box['label']}.")
            if vf.dist_m(box) > max_range:
                extra.append(f"Tâm hộp cách LiDAR hơn {max_range:g} m theo phương ngang.")
            if box.get("outside"):
                extra.append("Lab Day 13 không dùng thuộc tính Outside.")
            if any(vf.yaw_delta(box.get(axis, 0), 0) > math.radians(0.1) for axis in ("roll", "pitch")):
                extra.append("Hộp bị nghiêng (roll/pitch). Chỉ xoay yaw trong góc nhìn Top.")
            # For dimensions, the lab's reference table supersedes the generic selfcheck ranges.
            inherited = [flag for flag in result["flags"].split("; ") if flag and
                         not flag.startswith(("length=", "width=", "height="))]
            flags = "; ".join(inherited + extra)
            rows.append({"frame": frame, **result, "object_type": box.get("object_type", ""),
                         "score": score, "flags": flags})
    return rows


def write_review(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        fields = ("frame", "idx", "object_type", "label", "score", "dist_m", "points_in",
                  "ground_gap_m", "flags", "decision")
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main():
    vf.utf8_stdio()
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(required=True)
    predict = commands.add_parser("prelabel", help="Generate cuboid candidates")
    source = predict.add_mutually_exclusive_group(required=True)
    source.add_argument("--config", type=Path)
    source.add_argument("--predictions", type=Path, help="Read model predictions from JSON")
    predict.add_argument("--checkpoint", type=Path)
    predict.add_argument("--device", default="cuda:0")
    predict.add_argument("--score-min", type=float, default=0.15)
    predict.add_argument("--job", type=int, help="Append non-overlapping shapes to a CVAT 3D job")
    frames = predict.add_mutually_exclusive_group(required=True)
    frames.add_argument("--frames", type=Path, help="Directory of XYZI .bin frames in VF axes")
    frames.add_argument("--frame-manifest", type=Path, help="JSON object mapping frame names to local .bin paths")
    predict.set_defaults(run=prelabel)
    review = commands.add_parser("check", help="Generate a CSV review list")
    source = review.add_mutually_exclusive_group(required=True)
    source.add_argument("--input", type=Path, help="Read the JSON emitted by prelabel")
    source.add_argument("--job", type=int, help="Read saved cuboid Shapes from CVAT")
    review.add_argument("--score-review", type=float, default=0.35)
    review.add_argument("--frames", type=Path, required=True, help="Directory of XYZI .bin frames in VF axes")
    review.set_defaults(run=check)
    for command in (predict, review):
        command.add_argument("--out", type=Path, required=True)
        command.add_argument("--max-range", type=float, default=50.0)
    args = parser.parse_args()
    if not math.isfinite(args.max_range) or args.max_range <= 0:
        parser.error("--max-range must be positive and finite.")
    score = getattr(args, "score_min", getattr(args, "score_review", 0))
    if not 0 <= score <= 1:
        parser.error("The score threshold must be between 0 and 1.")
    try:
        args.run(args)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(1, f"Error: {exc}\n")


if __name__ == "__main__":
    main()
