"""Web application entry point for KeepGeneration Web.

This project is a derivative work based on KeepGeneration-Web and KeepSultan.
See the repository root README.md, NOTICE, and ATTRIBUTION.md for attribution
and license notes.
"""

from __future__ import annotations

import os
import secrets
import threading
import time
import uuid
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
import re

from flask import Flask, jsonify, render_template, request, send_file, url_for
from PIL import Image

from KeepSultan import (
    KeepConfig,
    KeepSultanApp,
    NumberRange,
    TimeRange,
    seconds_to_hms,
)


BASE_DIR = Path(__file__).resolve().parent


app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev_fallback_secret_key_change_me")
app.config["UPLOAD_FOLDER"] = str(BASE_DIR / "static" / "uploads")
app.config["OUTPUT_FOLDER"] = str(BASE_DIR / "generated_batches")
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024
app.config["FILE_MAX_AGE_SECONDS"] = int(os.environ.get("FILE_MAX_AGE_SECONDS", 1 * 60 * 60))
app.config["CLEANUP_INTERVAL_SECONDS"] = int(os.environ.get("CLEANUP_INTERVAL_SECONDS", 30 * 60))

DEFAULT_AVATAR = str(BASE_DIR / "static" / "default_avatar.png")

MAP_PRESETS = {
    "通用地图（无明显地理标识）": "static/maps/default.png",
    "SYSU东校园体育场1": "static/maps/map6.png",
    "SYSU东校园体育场2": "static/maps/map15.png",
    "SYSU东校园体育场3": "static/maps/map16.png",
    "SYSU东校园体育场4": "static/maps/map17.png",
    "SYSU东校园体育场5": "static/maps/map18.png",
    "SYSU东校园体育场6": "static/maps/map19.png",
    "SYSU东校园体育场7": "static/maps/map20.png",
    "SYSU东校园环形大圈": "static/maps/map7.png",
    "大学城中环路": "static/maps/map13.png",
    "SYSU南校园英东体育场": "static/maps/map4.png",
    "SYSU南校园大圈": "static/maps/map1.png",
    "SYSU南校园小圈": "static/maps/map2.png",
    "SYSU南校园中轴线": "static/maps/map3.png",
    "SYSU南校园珠江南岸": "static/maps/map5.png",
    "二沙岛": "static/maps/map12.png",
    "花城广场": "static/maps/map14.png",
    "SYSU珠海校区": "static/maps/map8.png",
    "苏州大学": "static/maps/map9.png",
    "中央财经大学": "static/maps/map10.png",
    "中南大学": "static/maps/map11.png",
}

SESSION_WINDOWS = {
    "noon": {
        "label": "中午",
        "default_start": "12:10",
        "default_end": "13:50",
    },
    "evening": {
        "label": "晚上",
        "default_start": "19:20",
        "default_end": "21:50",
    },
}

RANDOM_MAP_DIR = BASE_DIR / "static" / "maps" / "radom"
WEATHER_SEQUENCE = ["晴", "晴转多云", "多云", "阴"]
WEATHER_TEMPERATURE_OFFSETS = {
    "晴": 2,
    "晴转多云": 1,
    "多云": 0,
    "阴": -1,
}

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
os.makedirs(app.config["OUTPUT_FOLDER"], exist_ok=True)


DEFAULT_CONFIG = {
    "template": str(BASE_DIR / "static" / "default_template.png"),
    "map": str(BASE_DIR / "static" / "maps" / "default.png"),
    "username": "Keep User",
    "start_date": datetime.now().strftime("%Y-%m-%d"),
    "end_date": datetime.now().strftime("%Y-%m-%d"),
    "location": "广州市",
    "weather": "多云",
    "temperature": "20°C",
    "total_km": [4.0, 6.0],
    "pace_range": ["05:20", "06:10"],
    "total_time_buffer_minutes": [3, 8],
    "session_slots": ["noon"],
    "session_windows": {
        key: [cfg["default_start"], cfg["default_end"]]
        for key, cfg in SESSION_WINDOWS.items()
    },
    "cumulative_climb": {"base": 92, "fluctuation": 8},
    "average_cadence": {"base": 176, "fluctuation": 6},
    "exercise_load": {"base": 82, "fluctuation": 10},
    "random_map": {
        "enabled": False,
    },
}


def cleanup_old_files(folder_path: str, max_age_seconds: int):
    now = time.time()
    for root, _, files in os.walk(folder_path):
        for filename in files:
            file_path = os.path.join(root, filename)
            try:
                if not os.path.isfile(file_path):
                    continue
                if now - os.path.getmtime(file_path) > max_age_seconds:
                    os.remove(file_path)
                    app.logger.info("Removed stale file: %s", file_path)
            except FileNotFoundError:
                continue
            except Exception as exc:
                app.logger.warning("Failed to remove file %s: %s", file_path, exc)


def start_cleanup_scheduler():
    def _run_cleanup_loop():
        while True:
            try:
                max_age = app.config["FILE_MAX_AGE_SECONDS"]
                for folder in (app.config["UPLOAD_FOLDER"], app.config["OUTPUT_FOLDER"]):
                    cleanup_old_files(folder, max_age)
            except Exception as exc:
                app.logger.error("Error during scheduled cleanup: %s", exc)
            time.sleep(app.config["CLEANUP_INTERVAL_SECONDS"])

    thread = threading.Thread(target=_run_cleanup_loop, daemon=True, name="cleanup-worker")
    thread.start()
    return thread


if not app.debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
    start_cleanup_scheduler()


@app.route("/", methods=["GET"])
def index():
    random_map_files = list_random_map_files()
    random_map_preview = None
    if random_map_files:
        random_map_preview = url_for("static", filename=f"maps/radom/{random_map_files[0].name}")
    return render_template(
        "index.html",
        default_config=DEFAULT_CONFIG,
        map_presets=MAP_PRESETS,
        session_windows=SESSION_WINDOWS,
        random_map_count=len(random_map_files),
        random_map_preview=random_map_preview,
    )


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in {"png", "jpg", "jpeg", "webp"}


def resolve_asset_path(relative_path: str) -> str:
    return str(BASE_DIR / relative_path)


def list_random_map_files() -> list[Path]:
    if not RANDOM_MAP_DIR.exists():
        return []
    return sorted(
        [
            path
            for path in RANDOM_MAP_DIR.iterdir()
            if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}
        ]
    )


def handle_upload(field_name: str, file_type: str) -> str | None:
    if field_name not in request.files:
        return None
    file = request.files[field_name]
    if file.filename == "" or file.filename is None:
        return None
    if file and allowed_file(file.filename):
        img = Image.open(file.stream)
        img = img.convert("RGBA")
        filename = f"{file_type}_{uuid.uuid4().hex}.png"
        save_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        img.save(save_path, format="PNG")
        return save_path
    return None


def clamp_int(value: int, minimum: int) -> int:
    return max(minimum, int(round(value)))


def normalize_time_hm(value: str) -> str:
    cleaned = (value or "").strip()
    parts = cleaned.split(":")
    if len(parts) == 2:
        hour, minute = parts
        return f"{int(hour):02d}:{int(minute):02d}"
    if len(parts) == 3:
        hour, minute, _seconds = parts
        return f"{int(hour):02d}:{int(minute):02d}"
    raise ValueError(f"Invalid time value: {value}")


def parse_pace_to_seconds(value: str) -> int:
    cleaned = (value or "").strip()
    parts = cleaned.split(":")
    if len(parts) != 2:
        raise ValueError("配速格式必须为 mm:ss")
    minutes, seconds = map(int, parts)
    total = minutes * 60 + seconds
    if total <= 0:
        raise ValueError("配速必须大于 0")
    return total


def parse_date_range(start_date: str, end_date: str) -> list[datetime]:
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    if start_dt > end_dt:
        raise ValueError("结束日期不能早于开始日期")

    days = []
    cursor = start_dt
    while cursor <= end_dt:
        days.append(cursor)
        cursor += timedelta(days=1)
    return days


def choose_fixed_map_path() -> str:
    map_uploaded_path = handle_upload("custom_map", "map")
    if map_uploaded_path:
        return map_uploaded_path

    map_selection = request.form.get("map_preset", "").strip()
    if map_selection and map_selection in MAP_PRESETS:
        return resolve_asset_path(MAP_PRESETS[map_selection])
    return DEFAULT_CONFIG["map"]


def choose_random_map_path(random_maps: list[Path], previous_map: str | None) -> str:
    if not random_maps:
        raise ValueError(f"随机地图目录为空：{RANDOM_MAP_DIR}")

    candidates = [path for path in random_maps if str(path) != previous_map]
    if not candidates:
        candidates = random_maps
    return str(secrets.SystemRandom().choice(candidates))


def choose_avatar_path() -> str:
    avatar_uploaded_path = handle_upload("avatar", "avatar")
    return avatar_uploaded_path or DEFAULT_AVATAR


def get_form_value(key: str, default: str) -> str:
    value = request.form.get(key)
    if value is None:
        return default
    value = value.strip()
    return value or default


def get_float_value(key: str, default: float) -> float:
    return float(get_form_value(key, str(default)))


def get_int_value(key: str, default: int) -> int:
    return int(get_form_value(key, str(default)))


def random_float(low: float, high: float, precision: int = 2) -> float:
    if low > high:
        low, high = high, low
    return round(NumberRange(low, high, precision).sample(), precision)


def random_int(low: int, high: int) -> int:
    if low > high:
        low, high = high, low
    return int(NumberRange(low, high, 0).sample())


def sample_end_time(window_start: str, window_end: str) -> str:
    time_range = TimeRange(f"{normalize_time_hm(window_start)}:00", f"{normalize_time_hm(window_end)}:00")
    return time_range.sample()[:5]


def sample_weather() -> str:
    return secrets.SystemRandom().choice(WEATHER_SEQUENCE)


def parse_temperature_base(value: str) -> int:
    match = re.search(r"-?\d+", value or "")
    if not match:
        raise ValueError("温度格式需要包含数字，例如 20°C")
    return int(match.group(0))


def sample_temperature(base_temperature: int, weather: str) -> str:
    fluctuation = secrets.SystemRandom().randint(-1, 2)
    adjusted = base_temperature + WEATHER_TEMPERATURE_OFFSETS.get(weather, 0) + fluctuation
    return f"{adjusted}°C"


def build_metric_value(base: int, fluctuation: int, minimum: int, distance_factor: float = 1.0) -> int:
    randomized = base + random_int(-fluctuation, fluctuation)
    adjusted = int(round(randomized * distance_factor))
    return clamp_int(adjusted, minimum)


def build_generation_options() -> dict:
    slots = []
    if request.form.get("include_noon"):
        slots.append("noon")
    if request.form.get("include_evening"):
        slots.append("evening")
    if not slots:
        raise ValueError("请至少选择一个生成时段")

    km_min = get_float_value("total_km_min", DEFAULT_CONFIG["total_km"][0])
    km_max = get_float_value("total_km_max", DEFAULT_CONFIG["total_km"][1])
    pace_min = parse_pace_to_seconds(get_form_value("pace_min", DEFAULT_CONFIG["pace_range"][0]))
    pace_max = parse_pace_to_seconds(get_form_value("pace_max", DEFAULT_CONFIG["pace_range"][1]))
    buffer_min = get_int_value(
        "total_time_buffer_min",
        DEFAULT_CONFIG["total_time_buffer_minutes"][0],
    )
    buffer_max = get_int_value(
        "total_time_buffer_max",
        DEFAULT_CONFIG["total_time_buffer_minutes"][1],
    )

    if km_min <= 0 or km_max <= 0:
        raise ValueError("公里数范围必须大于 0")
    if buffer_min < 0 or buffer_max < 0:
        raise ValueError("总时长补时不能小于 0")
    if bool(request.form.get("random_map_enabled")) and not list_random_map_files():
        raise ValueError(f"随机地图目录为空：{RANDOM_MAP_DIR}")

    return {
        "username": get_form_value("username", DEFAULT_CONFIG["username"]),
        "start_date": get_form_value("start_date", DEFAULT_CONFIG["start_date"]),
        "end_date": get_form_value("end_date", DEFAULT_CONFIG["end_date"]),
        "location": get_form_value("location", DEFAULT_CONFIG["location"]),
        "weather": get_form_value("weather", DEFAULT_CONFIG["weather"]),
        "temperature_base": parse_temperature_base(get_form_value("temperature", DEFAULT_CONFIG["temperature"])),
        "slots": slots,
        "distance_range": [km_min, km_max],
        "pace_seconds_range": [pace_min, pace_max],
        "buffer_minutes_range": [buffer_min, buffer_max],
        "session_windows": {
            slot: [
                get_form_value(f"{slot}_start", DEFAULT_CONFIG["session_windows"][slot][0]),
                get_form_value(f"{slot}_end", DEFAULT_CONFIG["session_windows"][slot][1]),
            ]
            for slot in SESSION_WINDOWS
        },
        "metrics": {
            "cumulative_climb": {
                "base": get_int_value(
                    "cumulative_climb_base",
                    DEFAULT_CONFIG["cumulative_climb"]["base"],
                ),
                "fluctuation": get_int_value(
                    "cumulative_climb_fluctuation",
                    DEFAULT_CONFIG["cumulative_climb"]["fluctuation"],
                ),
                "minimum": 0,
            },
            "average_cadence": {
                "base": get_int_value(
                    "average_cadence_base",
                    DEFAULT_CONFIG["average_cadence"]["base"],
                ),
                "fluctuation": get_int_value(
                    "average_cadence_fluctuation",
                    DEFAULT_CONFIG["average_cadence"]["fluctuation"],
                ),
                "minimum": 1,
            },
            "exercise_load": {
                "base": get_int_value(
                    "exercise_load_base",
                    DEFAULT_CONFIG["exercise_load"]["base"],
                ),
                "fluctuation": get_int_value(
                    "exercise_load_fluctuation",
                    DEFAULT_CONFIG["exercise_load"]["fluctuation"],
                ),
                "minimum": 1,
            },
        },
        "random_map": {
            "enabled": bool(request.form.get("random_map_enabled")),
            "files": list_random_map_files(),
        },
    }


def build_run_payload(run_date: datetime, slot: str, options: dict) -> dict:
    km_low, km_high = options["distance_range"]
    pace_low, pace_high = options["pace_seconds_range"]
    buffer_low, buffer_high = options["buffer_minutes_range"]
    reference_distance = max((km_low + km_high) / 2, 0.1)

    total_km = random_float(km_low, km_high, 2)
    pace_seconds = random_int(pace_low, pace_high)
    sport_seconds = max(60, int(round(total_km * pace_seconds)))
    extra_seconds = random_int(buffer_low * 60, buffer_high * 60)
    total_seconds = sport_seconds + extra_seconds

    window_start, window_end = options["session_windows"][slot]
    end_time = sample_end_time(window_start, window_end)
    distance_factor = min(max(total_km / reference_distance, 0.85), 1.18)
    load_factor = min(max(total_seconds / max(sport_seconds, 1), 1.0), 1.25)
    cumulative_climb = build_metric_value(
        options["metrics"]["cumulative_climb"]["base"],
        options["metrics"]["cumulative_climb"]["fluctuation"],
        options["metrics"]["cumulative_climb"]["minimum"],
        distance_factor,
    )
    average_cadence = build_metric_value(
        options["metrics"]["average_cadence"]["base"],
        options["metrics"]["average_cadence"]["fluctuation"],
        options["metrics"]["average_cadence"]["minimum"],
    )
    exercise_load = build_metric_value(
        options["metrics"]["exercise_load"]["base"],
        options["metrics"]["exercise_load"]["fluctuation"],
        options["metrics"]["exercise_load"]["minimum"],
        load_factor,
    )

    weather = sample_weather()

    return {
        "username": options["username"],
        "date": run_date.strftime("%Y-%m-%d"),
        "location": options["location"],
        "weather": weather,
        "temperature": sample_temperature(options["temperature_base"], weather),
        "end_time": end_time,
        "total_km": [total_km, total_km],
        "sport_time": [seconds_to_hms(sport_seconds), seconds_to_hms(sport_seconds)],
        "total_time": [seconds_to_hms(total_seconds), seconds_to_hms(total_seconds)],
        "cumulative_climb": [cumulative_climb, cumulative_climb],
        "average_cadence": [average_cadence, average_cadence],
        "exercise_load": [exercise_load, exercise_load],
        "slot": slot,
        "slot_label": SESSION_WINDOWS[slot]["label"],
    }


def generate_image(template_path: str, map_path: str, avatar_path: str, params: dict, output_path: str):
    cfg = KeepConfig(
        template=template_path,
        map=map_path,
        avatar=avatar_path,
        username=params["username"],
        date=params["date"].replace("-", "/"),
        location=params["location"],
        weather=params["weather"],
        temperature=params["temperature"],
        end_time=params["end_time"],
        total_km=NumberRange(params["total_km"][0], params["total_km"][1], 2),
        sport_time=TimeRange(params["sport_time"][0], params["sport_time"][1]),
        total_time=TimeRange(params["total_time"][0], params["total_time"][1]),
        cumulative_climb=NumberRange(params["cumulative_climb"][0], params["cumulative_climb"][1], 0),
        average_cadence=NumberRange(params["average_cadence"][0], params["average_cadence"][1], 0),
        exercise_load=NumberRange(params["exercise_load"][0], params["exercise_load"][1], 0),
    )

    app_instance = KeepSultanApp(cfg)
    app_instance.process()
    app_instance.save(output_path)


def build_zip_archive(zip_path: Path, files: list[Path]):
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file_path in files:
            archive.write(file_path, arcname=file_path.name)


@app.route("/api/generate", methods=["POST"])
def api_generate():
    try:
        fixed_map_path = choose_fixed_map_path()
        avatar_path = choose_avatar_path()
        options = build_generation_options()
        dates = parse_date_range(options["start_date"], options["end_date"])

        batch_id = datetime.now().strftime("%Y%m%d%H%M%S") + "_" + uuid.uuid4().hex[:8]
        batch_folder = Path(app.config["OUTPUT_FOLDER"]) / batch_id
        batch_folder.mkdir(parents=True, exist_ok=True)
        generated_files: list[Path] = []
        image_items = []
        previous_map_path: str | None = None

        for run_date in dates:
            for slot in options["slots"]:
                params = build_run_payload(run_date, slot, options)
                map_path = fixed_map_path
                if options["random_map"]["enabled"]:
                    map_path = choose_random_map_path(options["random_map"]["files"], previous_map_path)
                previous_map_path = map_path
                output_filename = f"keep_{run_date.strftime('%Y%m%d')}_{slot}_{uuid.uuid4().hex[:6]}.png"
                output_path = batch_folder / output_filename
                generate_image(
                    DEFAULT_CONFIG["template"],
                    map_path,
                    avatar_path,
                    params,
                    str(output_path),
                )
                generated_files.append(output_path)
                image_items.append(
                    {
                        "date": params["date"],
                        "slot": slot,
                        "slot_label": params["slot_label"],
                        "preview_url": url_for("serve_output", filename=f"{batch_id}/{output_filename}"),
                        "download_url": url_for("download", filename=f"{batch_id}/{output_filename}"),
                        "filename": output_filename,
                        "summary": (
                            f'{params["date"]} {params["slot_label"]} · '
                            f'{params["total_km"][0]:.2f} km · '
                            f'{params["sport_time"][0]} · '
                            f'{params["end_time"]}'
                        ),
                    }
                )

        zip_filename = f"keep_batch_{batch_id}.zip"
        zip_path = batch_folder / zip_filename
        build_zip_archive(zip_path, generated_files)

        return jsonify(
            {
                "success": True,
                "generated_count": len(image_items),
                "images": image_items,
                "batch_download_url": url_for("download", filename=f"{batch_id}/{zip_filename}"),
                "save_dir": str(batch_folder),
            }
        )
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@app.route("/output/<path:filename>", methods=["GET"])
def serve_output(filename):
    return send_file(os.path.join(app.config["OUTPUT_FOLDER"], filename), as_attachment=False)


@app.route("/download/<path:filename>", methods=["GET"])
def download(filename):
    suffix = Path(filename).suffix.lower()
    if suffix == ".zip":
        download_name = Path(filename).name
    else:
        download_name = Path(filename).name
    return send_file(
        os.path.join(app.config["OUTPUT_FOLDER"], filename),
        as_attachment=True,
        download_name=download_name,
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5010, debug=False)
