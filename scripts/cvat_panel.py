"""Run the local service for the CVAT cuboid panel browser extension."""
from __future__ import annotations

import argparse
import configparser
import json
import math
import os
import re
import secrets
import shutil
import subprocess
import threading
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

from cvat_sdk.exceptions import ApiException

import annotation_pipeline as pipeline
import lab
from vf_cvat import frame_sources

ROOT = pipeline.ROOT
WORK = ROOT / "work" / "cvat-panel"
PORT = 8765
ROUTE = re.compile(r"/jobs/([1-9][0-9]*)(?:/(check|prelabel))?")
MEASURE_ROUTE = re.compile(r"/jobs/([1-9][0-9]*)/(distances|points/([0-9]+))")


def prepare_extension(work):
    work.mkdir(parents=True, exist_ok=True)
    key_path = work / "panel.key"
    try:
        with key_path.open("x", encoding="ascii") as handle:
            handle.write(secrets.token_urlsafe(32))
    except FileExistsError:
        pass
    key = key_path.read_text(encoding="ascii").strip()
    if not key:
        raise ValueError(f"Empty panel key in {key_path}.")
    extension = work / "extension"
    shutil.copytree(ROOT / "cvat" / "panel-extension", extension, dirs_exist_ok=True)
    (extension / "settings.js").write_text(
        f"const PANEL_KEY = {json.dumps(key)};\n", encoding="utf-8",
    )
    return key, extension


def check_paths(folder, task_name):
    if (folder / "points").is_dir():
        return pipeline.scan_files(folder / "points")
    cfg = lab.load_config()
    if task_name == pipeline.vf.task_name(cfg["student"]):
        sources = frame_sources(lab.data_dir(cfg), cfg["student"])
        return {frame["name"]: frame["lidar"] for frame in sources}
    raise ValueError(f"Đặt các file .bin dùng cho job này trong {folder / 'points'}.")


def generate_predictions(folder, paths):
    output = folder / "prelabels.json"
    predictions = folder / "model-output.json"
    if not predictions.is_file():
        settings = configparser.ConfigParser(interpolation=None)
        ini = folder / "model.ini"
        if not settings.read(ini, encoding="utf-8-sig") or "model" not in settings:
            raise ValueError(f"Thêm model.ini hoặc model-output.json trong {folder}.")
        model = settings["model"]
        backend = model.get("backend", "mmdet3d").strip()
        if backend not in ("mmdet3d", "autoware_onnx"):
            raise ValueError(f"Backend không được hỗ trợ trong {ini}: {backend}.")
        required_files = ("python", "config", "checkpoint") if backend == "mmdet3d" else ("python",)
        required_dirs = () if backend == "mmdet3d" else ("models", "runtime")
        files = {}
        missing = []
        for name in (*required_files, *required_dirs):
            value = model.get(name, "").strip().strip('"').strip("'")
            path = (folder / Path(value).expanduser()).resolve() if value else None
            exists = path and (path.is_dir() if name in required_dirs else path.is_file())
            if exists:
                files[name] = path
            else:
                missing.append(name)
        if missing:
            raise ValueError(f"Chưa có model chạy được cho job này. Điền đường dẫn file cho "
                             f"{', '.join(missing)} trong {ini}, hoặc đặt model-output.json từ model đã chạy.")
        manifest = folder / "frame-paths.json"
        manifest.write_text(json.dumps({frame: str(path.resolve()) for frame, path in paths.items()}),
                            encoding="utf-8")
        if backend == "autoware_onnx":
            predictions = folder / "cpu-predictions.json"
            command = [
                str(files["python"]), str(ROOT / "scripts" / "autoware_centerpoint.py"),
                "--frame-manifest", str(manifest), "--out", str(predictions),
                "--models", str(files["models"]), "--runtime", str(files["runtime"]),
            ]
        else:
            command = [
                str(files["python"]), str(ROOT / "scripts" / "annotation_pipeline.py"), "prelabel",
                "--frame-manifest", str(manifest), "--out", str(output),
                "--config", str(files["config"]), "--checkpoint", str(files["checkpoint"]),
                "--device", model.get("device", "cuda:0"),
            ]
        log = folder / "model.log"
        model_env = os.environ.copy()
        model_env.pop("CVAT_ACCESS_TOKEN", None)
        with log.open("w", encoding="utf-8") as handle:
            result = subprocess.run(
                command, cwd=folder, stdout=handle, stderr=subprocess.STDOUT, env=model_env,
            )
        if result.returncode:
            raise ValueError(f"Model chưa chạy xong. Xem {log}.")
    if predictions.is_file():
        pipeline.prelabel(SimpleNamespace(
            predictions=predictions, out=output, job=None,
            score_min=0.15, max_range=50.0,
        ), paths=paths)
    return json.loads(output.read_text(encoding="utf-8"))["frames"]


def run_job(action, job_id, work):
    folder = work / "jobs" / str(job_id)
    with pipeline.cvat_client() as client:
        job = client.jobs.retrieve(job_id)
        task = client.tasks.retrieve(job.task_id)
        indices = pipeline.job_frames(job, task)
        if action == "check":
            shapes, annotation_issues = pipeline.read_annotations(job, task, indices)
            minimums = pipeline.lab_minimums(task.name, indices)

    paths = check_paths(folder, task.name)
    if action == "prelabel":
        if paths.keys() != indices.keys():
            raise ValueError("Tên frame trong nguồn LiDAR phải khớp với job CVAT.")
        frames = generate_predictions(folder, paths)
        added, duplicates = pipeline.seed_job(job_id, frames)
        pending = [
            {
                "frame": frame, "frame_index": indices[frame], "label": box["source_label"],
                "idx": box["idx"], "flags": f"Xác nhận người lái (~{pipeline.vf.dist_m(box):.1f} m).",
            }
            for frame, boxes in frames.items() for box in boxes if box["confirm_rider"]
        ]
        return {
            "message": f"Đã thêm {added} Shape. Bỏ qua {duplicates} dự đoán trùng hộp. "
                       f"Có {len(pending)} ứng viên xe hai bánh cần xác nhận người lái.",
            "reload": bool(added),
            "flags": pending,
        }

    rows = pipeline.review_frames(paths, shapes, minimums=minimums)
    rows.extend(annotation_issues)
    flagged = [row for row in rows if row["flags"]]
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    report = folder / f"review-{timestamp}.csv"
    pipeline.write_review(report, rows)
    message = f"{len(flagged)} mục cần xem lại trên {len(shapes)} frame."
    if minimums:
        total = sum(not box["outside"] for boxes in shapes.values() for box in boxes)
        message += f" Đã lưu {total} Shape (yêu cầu ít nhất {sum(minimums.values())} trên 10 frame)."
    return {
        "message": message,
        "report": report.relative_to(ROOT).as_posix(),
        "flags": [{**row, "frame_index": indices[row["frame"]]} for row in flagged],
        "manual_review": pipeline.MANUAL_REVIEW,
    }


def measurements(job_id, work, frame_index=None):
    with pipeline.cvat_client() as client:
        job = client.jobs.retrieve(job_id)
        task = client.tasks.retrieve(job.task_id)
        indices = pipeline.job_frames(job, task)
        if frame_index is None:
            shapes, _ = pipeline.read_annotations(job, task, indices)
            return {"frames": [
                {"name": frame, "index": index, "objects": sorted([
                    {"idx": box["idx"], "label": box["label"],
                     "horizontal_m": round(pipeline.vf.dist_m(box), 2),
                     "spatial_m": round(math.hypot(box["x"], box["y"], box["z"]), 2)}
                    for box in shapes[frame] if not box.get("outside")
                ], key=lambda box: box["horizontal_m"])}
                for frame, index in sorted(indices.items(), key=lambda item: item[1])
            ]}
    name = next((frame for frame, index in indices.items() if index == frame_index), None)
    if name is None:
        raise ValueError("Frame không thuộc job này.")
    paths = check_paths(work / "jobs" / str(job_id), task.name)
    if name not in paths:
        raise ValueError(f"Thiếu point cloud của frame {name}.")
    points = [point for point in pipeline.qa.points_xyz(paths[name])
              if all(math.isfinite(v) for v in point) and max(abs(point[0]), abs(point[1])) <= 50]
    stride = max(1, math.ceil(len(points) / 15000))
    return {"points": [[round(coordinate, 3) for coordinate in point] for point in points[::stride]]}


class Panel:
    def __init__(self, key, work=WORK):
        self.key = f"Bearer {key}".encode()
        self.work = work
        self.lock = threading.Lock()
        self.runs = {}
        self.executor = ThreadPoolExecutor(max_workers=1)

    def status(self, job_id):
        with self.lock:
            return self.runs.get(job_id, {"state": "idle"})

    def start(self, job_id, action):
        with self.lock:
            if self.runs.get(job_id, {}).get("state") == "running":
                return False
            self.runs[job_id] = {"state": "running", "action": action}
            self.executor.submit(self.run, job_id, action)
            return True

    def run(self, job_id, action):
        try:
            result = {"state": "done", **run_job(action, job_id, self.work)}
        except ApiException as exc:
            result = {"state": "error", "message": f"API CVAT trả về HTTP {exc.status}."}
        except (OSError, ValueError, KeyError, SystemExit) as exc:
            result = {"state": "error", "message": str(exc)}
        except Exception:
            result = {"state": "error", "message": "Lỗi khi chạy công cụ. Xem terminal chạy dịch vụ."}
            traceback.print_exc()
        with self.lock:
            self.runs[job_id] = {"action": action, **result}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.respond(post=False)

    def do_POST(self):
        self.respond(post=True)

    def respond(self, *, post):
        panel = self.server.panel
        authorization = self.headers.get("Authorization", "").encode()
        route = ROUTE.fullmatch(self.path)
        if not secrets.compare_digest(authorization, panel.key):
            self.send_json(401, {"message": "Panel chưa được ghép với dịch vụ local."})
        elif not post and (measure := MEASURE_ROUTE.fullmatch(self.path)):
            frame_index = int(measure[3]) if measure[3] is not None else None
            try:
                result = measurements(int(measure[1]), panel.work, frame_index)
            except ApiException as exc:
                self.send_json(502, {"message": f"API CVAT trả về HTTP {exc.status}."})
            except (OSError, ValueError, KeyError, SystemExit) as exc:
                self.send_json(400, {"message": str(exc)})
            else:
                self.send_json(200, result)
        elif not route or post != bool(route[2]):
            self.send_json(404, {"message": "Đường dẫn không hợp lệ."})
        else:
            job_id = int(route[1])
            if post and not panel.start(job_id, route[2]):
                self.send_json(409, {"message": "Job đang chạy một thao tác."})
            else:
                self.send_json(202 if post else 200, panel.status(job_id))

    def send_json(self, status, data):
        content = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, *_):
        pass


def main():
    pipeline.vf.utf8_stdio()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    key, extension = prepare_extension(WORK)
    print(f"Edge extension: {extension}", flush=True)
    if not args.prepare_only:
        with ThreadingHTTPServer(("127.0.0.1", PORT), Handler) as server:
            server.panel = Panel(key)
            print(f"CVAT panel service: http://127.0.0.1:{PORT}", flush=True)
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass
            finally:
                server.panel.executor.shutdown()


if __name__ == "__main__":
    main()
