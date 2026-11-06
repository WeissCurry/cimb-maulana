"""Flask backend for the daily task board, JSON API, and database models."""

from __future__ import annotations

import calendar
import click
import json
import os
import re
from datetime import date, datetime, timedelta, timezone
from typing import Any, Mapping
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from flask import (
    Blueprint,
    Flask,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import case

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

db = SQLAlchemy()

STAGES = [
    ("todo", "Belum Mulai"),
    ("in_progress", "Dikerjakan"),
    ("ready", "Siap Dicek"),
    ("review", "Review"),
    ("done", "Selesai"),
]
STAGE_LABELS = dict(STAGES)
STATUS_KEYS = tuple(key for key, _ in STAGES)
PRIORITIES = ("low", "medium", "high")
VIEWS = ("board", "list", "calendar", "gantt")
TITLE_MAX = 200
DESCRIPTION_MAX = 2000

WIB = ZoneInfo("Asia/Jakarta")
MONTHS_SHORT = (
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "Mei",
    "Jun",
    "Jul",
    "Agu",
    "Sep",
    "Okt",
    "Nov",
    "Des",
)
MONTHS_LONG = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)

DEFAULT_DATABASE_URL = (
    "mysql+pymysql://todo_user:todo_pass@127.0.0.1:3306/todo_db"
)
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MONTH_PATTERN = re.compile(r"^(\d{4})-(\d{2})$")
SAFE_NEXT_PATTERN = re.compile(r"^/[^/\\]")
BACKSLASH_PATTERN = re.compile(r"\\|%5c", re.IGNORECASE)
CONTROL_PATTERN = re.compile(r"[\x00-\x1f\x7f-\x9f]")
MIN_MONTH = (1, 2)
MAX_MONTH = (9999, 11)

SEED_TASKS: tuple[dict[str, Any], ...] = (
    {
        "title": "Perbarui daftar kontak darurat cabang",
        "description": "Verifikasi nomor PIC dan kontak cadangan tiap cabang.",
        "priority": "high",
        "status": "in_progress",
        "due_in_days": 2,
        "history": [("todo", 8), ("in_progress", 4)],
    },
    {
        "title": "Uji coba call tree tim operasional",
        "description": "Lakukan panggilan berantai dan catat waktu respons.",
        "priority": "high",
        "status": "ready",
        "due_in_days": 5,
        "history": [("todo", 10), ("in_progress", 6), ("ready", 1)],
    },
    {
        "title": "Review dokumen BIA unit Treasury",
        "description": "Periksa asumsi dampak dan RTO pada draf BIA.",
        "priority": "medium",
        "status": "review",
        "due_in_days": 3,
        "history": [
            ("todo", 12),
            ("in_progress", 8),
            ("ready", 3),
            ("review", 1),
        ],
    },
    {
        "title": "Simulasi failover server core banking",
        "description": "Uji perpindahan ke server cadangan saat jam sepi.",
        "priority": "high",
        "status": "in_progress",
        "due_in_days": 10,
        "history": [("todo", 6), ("in_progress", 2)],
    },
    {
        "title": "Rekap hasil drill evakuasi gedung",
        "description": "Susun temuan, waktu evakuasi, dan rekomendasi perbaikan.",
        "priority": "medium",
        "status": "done",
        "due_in_days": -3,
        "history": [
            ("todo", 15),
            ("in_progress", 12),
            ("ready", 9),
            ("review", 6),
            ("done", 4),
        ],
    },
    {
        "title": "Susun notulen rapat BCM mingguan",
        "description": "Rangkum keputusan dan action item rapat.",
        "priority": "low",
        "status": "done",
        "due_in_days": -1,
        "history": [
            ("todo", 5),
            ("in_progress", 3),
            ("ready", 2),
            ("done", 1),
        ],
    },
    {
        "title": "Pemetaan proses kritikal divisi Operations",
        "description": "Identifikasi proses dan dependensi yang wajib pulih lebih dulu.",
        "priority": "medium",
        "status": "todo",
        "due_in_days": 7,
        "history": [("todo", 2)],
    },
    {
        "title": "Cek kesiapan genset dan UPS data center",
        "description": "Pastikan bahan bakar, beban, dan jadwal pemeliharaan sesuai.",
        "priority": "high",
        "status": "todo",
        "due_in_days": 4,
        "history": [("todo", 1)],
    },
    {
        "title": "Validasi daftar aplikasi pendukung layanan",
        "description": "Cocokkan inventaris aplikasi dengan CMDB.",
        "priority": "low",
        "status": "todo",
        "due_in_days": 18,
        "history": [("todo", 3)],
    },
    {
        "title": "Perbarui prosedur kontak darurat vendor",
        "description": "Lengkapi eskalasi dan kontak layanan vendor kritikal.",
        "priority": "medium",
        "status": "in_progress",
        "due_in_days": -2,
        "history": [("todo", 9), ("in_progress", 5)],
    },
    {
        "title": "Latihan tabletop skenario gangguan jaringan",
        "description": "Siapkan skenario, peserta, dan daftar keputusan latihan.",
        "priority": "high",
        "status": "review",
        "due_in_days": 14,
        "history": [
            ("todo", 11),
            ("in_progress", 7),
            ("ready", 4),
            ("review", 2),
        ],
    },
    {
        "title": "Audit kesesuaian dokumen BCP dengan ISO 22301",
        "description": "Tandai klausul yang belum terpenuhi dan usulkan perbaikan.",
        "priority": "medium",
        "status": "ready",
        "due_in_days": 21,
        "history": [("todo", 13), ("in_progress", 10), ("ready", 2)],
    },
    {
        "title": "Susun jadwal sosialisasi BCM untuk staf baru",
        "description": "Siapkan materi singkat dan jadwal sesi per unit.",
        "priority": "low",
        "status": "in_progress",
        "due_in_days": None,
        "history": [("todo", 7), ("in_progress", 3)],
    },
    {
        "title": "Dokumentasikan lessons learned insiden bulan lalu",
        "description": "Kumpulkan kronologi dan usulan pencegahan berulang.",
        "priority": "medium",
        "status": "todo",
        "due_in_days": None,
        "history": [("todo", 6)],
    },
)


def _utcnow() -> datetime:
    """Return naive UTC to match MySQL DATETIME columns."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _today_wib() -> date:
    return datetime.now(WIB).date()


def _safe_date_offset(value: date, days: int) -> date:
    """Offset a date without crossing date.min or date.max."""
    try:
        return value + timedelta(days=days)
    except OverflowError:
        return date.max if days > 0 else date.min


def _to_wib(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(WIB)


def _iso_z(value: datetime | None) -> str | None:
    """Serialize UTC datetimes as ISO 8601 with a Z suffix."""
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def format_wib(value: datetime | date | None) -> str:
    """Render UTC datetimes in Asia/Jakarta."""
    if value is None:
        return ""
    if isinstance(value, datetime):
        moment = value
    elif isinstance(value, date):
        moment = datetime.combine(value, datetime.min.time())
    else:
        return ""
    moment = _to_wib(moment)
    return (
        f"{moment.day} {MONTHS_SHORT[moment.month - 1]} "
        f"{moment.year}, {moment:%H:%M}"
    )


def format_tanggal(value: date | datetime | None) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        value = value.date()
    if not isinstance(value, date):
        return ""
    return f"{value.day} {MONTHS_SHORT[value.month - 1]} {value.year}"


def format_durasi(minutes: int | None) -> str:
    if minutes is None:
        return ""
    try:
        total = int(minutes)
    except (TypeError, ValueError):
        return ""
    if total < 0:
        total = 0
    days, remainder = divmod(total, 24 * 60)
    hours, mins = divmod(remainder, 60)

    parts: list[str] = []
    if days:
        parts.append(f"{days} hari")
    if hours:
        parts.append(f"{hours} jam")
    if mins or not parts:
        parts.append(f"{mins} menit")
    return " ".join(parts)


def _stage_enum() -> db.Enum:
    return db.Enum(*STATUS_KEYS, name="task_status")


class Task(db.Model):
    __tablename__ = "tasks"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    title = db.Column(db.String(TITLE_MAX), nullable=False)
    description = db.Column(db.Text, nullable=True)
    due_date = db.Column(db.Date, nullable=True)
    priority = db.Column(
        db.Enum(*PRIORITIES, name="task_priority"),
        nullable=False,
        default="medium",
        server_default="medium",
    )
    status = db.Column(
        _stage_enum(),
        nullable=False,
        default="todo",
        server_default="todo",
    )
    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=_utcnow,
        server_default=db.func.current_timestamp(),
    )
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
        server_default=db.func.current_timestamp(),
    )

    events = db.relationship(
        "TaskEvent",
        back_populates="task",
        cascade="all, delete-orphan",
        order_by="TaskEvent.id",
    )

    @property
    def is_overdue(self) -> bool:
        return (
            self.status != "done"
            and self.due_date is not None
            and self.due_date < _today_wib()
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "priority": self.priority,
            "status": self.status,
            "status_label": STAGE_LABELS.get(self.status, self.status),
            "is_overdue": self.is_overdue,
            "created_at": _iso_z(self.created_at),
            "updated_at": _iso_z(self.updated_at),
        }


class TaskEvent(db.Model):
    __tablename__ = "task_events"
    __table_args__ = (
        db.Index(
            "ix_task_events_task_id_created_at", "task_id", "created_at"
        ),
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    task_id = db.Column(
        db.Integer,
        db.ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
    )
    from_status = db.Column(_stage_enum(), nullable=True)
    to_status = db.Column(_stage_enum(), nullable=False)
    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=_utcnow,
        server_default=db.func.current_timestamp(),
    )

    task = db.relationship("Task", back_populates="events")


class ValidationError(Exception):
    """Validation failure returned as a JSON 400 response."""

    def __init__(
        self, message: str, fields: Mapping[str, str] | None = None
    ) -> None:
        super().__init__(message)
        self.message = message
        self.fields = dict(fields or {})


bp = Blueprint("main", __name__)


def _add_event(
    task: Task,
    from_status: str | None,
    to_status: str,
    created_at: datetime | None = None,
) -> TaskEvent:
    event = TaskEvent(
        task_id=task.id,
        from_status=from_status,
        to_status=to_status,
        created_at=created_at or _utcnow(),
    )
    db.session.add(event)
    return event


def _move_task(task: Task, new_status: str) -> bool:
    """Change status and record an event; a same-status move writes none."""
    if new_status == task.status:
        return False
    old_status = task.status
    task.status = new_status
    _add_event(task, old_status, new_status)
    return True


def _task_events(task: Task) -> list[TaskEvent]:
    return list(
        db.session.scalars(
            db.select(TaskEvent)
            .where(TaskEvent.task_id == task.id)
            .order_by(TaskEvent.created_at.asc(), TaskEvent.id.asc())
        ).all()
    )


def timeline(task: Task, now: datetime | None = None) -> list[dict[str, Any]]:
    """Return stage history oldest first, with time spent in each stage."""
    events = _task_events(task)
    current = _to_wib(now) if now is not None else datetime.now(WIB)

    items: list[dict[str, Any]] = []
    for index, event in enumerate(events):
        entered_at = _to_wib(event.created_at)
        left_at = (
            _to_wib(events[index + 1].created_at)
            if index + 1 < len(events)
            else None
        )
        end = left_at if left_at is not None else current
        duration = int((end - entered_at).total_seconds() // 60)
        if duration < 0:
            duration = 0
        items.append(
            {
                "status": event.to_status,
                "label": STAGE_LABELS.get(
                    event.to_status, event.to_status
                ),
                "entered_at": entered_at,
                "left_at": left_at,
                "duration_minutes": duration,
            }
        )
    return items


def _status_error() -> str:
    return f"Status harus salah satu dari: {', '.join(STATUS_KEYS)}."


def _validate_task(
    payload: Mapping[str, Any], *, partial: bool = False
) -> dict[str, Any]:
    """Validate form or JSON payloads; partial updates only touch sent fields."""
    errors: dict[str, str] = {}
    values: dict[str, Any] = {}

    if not partial or "title" in payload:
        raw_title = payload.get("title")
        if raw_title is None:
            errors["title"] = "Judul wajib diisi."
        elif not isinstance(raw_title, str):
            errors["title"] = "Judul harus berupa teks."
        else:
            title = raw_title.strip()
            if not title:
                errors["title"] = "Judul wajib diisi."
            elif len(title) > TITLE_MAX:
                errors["title"] = f"Judul maksimal {TITLE_MAX} karakter."
            else:
                values["title"] = title

    if "description" in payload:
        raw_description = payload["description"]
        if raw_description is None:
            values["description"] = None
        elif not isinstance(raw_description, str):
            errors["description"] = "Deskripsi harus berupa teks."
        else:
            description = raw_description.strip()
            if len(description) > DESCRIPTION_MAX:
                errors["description"] = (
                    f"Deskripsi maksimal {DESCRIPTION_MAX} karakter."
                )
            else:
                values["description"] = description or None
    elif not partial:
        values["description"] = None

    if "due_date" in payload:
        raw_due_date = payload["due_date"]
        if raw_due_date is None:
            values["due_date"] = None
        elif not isinstance(raw_due_date, str):
            errors["due_date"] = "Format tanggal harus YYYY-MM-DD."
        elif not raw_due_date.strip():
            values["due_date"] = None
        else:
            due_date_text = raw_due_date.strip()
            if not DATE_PATTERN.match(due_date_text):
                errors["due_date"] = "Format tanggal harus YYYY-MM-DD."
            else:
                try:
                    values["due_date"] = datetime.strptime(
                        due_date_text, "%Y-%m-%d"
                    ).date()
                except ValueError:
                    errors["due_date"] = "Format tanggal harus YYYY-MM-DD."
    elif not partial:
        values["due_date"] = None

    if "priority" in payload:
        raw_priority = payload["priority"]
        if isinstance(raw_priority, str) and raw_priority.strip():
            priority = raw_priority.strip().lower()
        else:
            priority = ""
        if priority in PRIORITIES:
            values["priority"] = priority
        else:
            errors["priority"] = (
                "Prioritas harus salah satu dari: low, medium, high."
            )
    elif not partial:
        values["priority"] = "medium"

    if "status" in payload:
        raw_status = payload["status"]
        if isinstance(raw_status, str) and raw_status.strip():
            status = raw_status.strip().lower()
        else:
            status = ""
        if status in STAGE_LABELS:
            values["status"] = status
        else:
            errors["status"] = _status_error()
    elif not partial:
        values["status"] = "todo"

    if errors:
        raise ValidationError("Data tidak valid.", errors)

    return values


def _read_json_payload() -> dict[str, Any]:
    raw = request.get_data(cache=True)
    if not raw or not raw.strip():
        raise ValidationError("Body JSON tidak boleh kosong.")
    if not request.is_json:
        raise ValidationError(
            "Body harus menggunakan Content-Type application/json."
        )
    try:
        payload = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        raise ValidationError("Body harus berupa JSON yang valid.") from None
    if not isinstance(payload, dict):
        raise ValidationError("Body JSON harus berupa objek.")
    return payload


def _filter_strict(
    raw: str | None, name: str, allowed: tuple[str, ...]
) -> str:
    if raw is None:
        return "all"
    value = raw.strip().lower()
    if value in ("", "all"):
        return "all"
    if value in allowed:
        return value
    options = ", ".join(("all",) + allowed)
    raise ValidationError(
        f"Filter {name} tidak valid.",
        {name: f"Filter {name} harus salah satu dari: {options}."},
    )


def _filter_lenient(raw: str | None, allowed: tuple[str, ...]) -> str:
    if raw is None:
        return "all"
    value = raw.strip().lower()
    if value in allowed:
        return value
    return "all"


def _stage_rank():
    mapping = {key: index for index, (key, _) in enumerate(STAGES)}
    return case(mapping, value=Task.status, else_=len(STAGES))


def _priority_rank():
    return case(
        (Task.priority == "high", 0),
        (Task.priority == "medium", 1),
        else_=2,
    )


def _due_null_rank():
    return case((Task.due_date.is_(None), 1), else_=0)


def _task_query(status: str = "all", priority: str = "all"):
    statement = db.select(Task)
    if status != "all":
        statement = statement.where(Task.status == status)
    if priority != "all":
        statement = statement.where(Task.priority == priority)

    return statement.order_by(
        _stage_rank(),
        _due_null_rank(),
        Task.due_date.asc(),
        _priority_rank(),
        Task.created_at.desc(),
        Task.id.desc(),
    )


def _count_tasks(status: str | None = None) -> int:
    statement = db.select(db.func.count(Task.id))
    if status is not None:
        statement = statement.where(Task.status == status)
    return db.session.scalar(statement) or 0


def _counts() -> dict[str, int]:
    result = {"all": _count_tasks()}
    for key, _ in STAGES:
        result[key] = _count_tasks(key)
    return result


def _get_task_or_404(task_id: int) -> Task:
    task = db.session.get(Task, task_id)
    if task is None:
        abort(404)
    return task


def _next_url() -> str:
    target = (request.form.get("next") or "").strip()
    if (
        BACKSLASH_PATTERN.search(target)
        or CONTROL_PATTERN.search(target)
        or SAFE_NEXT_PATTERN.match(target) is None
    ):
        return url_for("main.index")
    return target


def _parse_view(raw: str | None) -> str:
    value = (raw or "").strip().lower()
    if value in VIEWS:
        return value
    return "board"


def _fetch_tasks(priority: str = "all") -> list[Task]:
    return list(db.session.scalars(_task_query("all", priority)).all())


def _board_columns_from(tasks: list[Task]) -> list[dict[str, Any]]:
    grouped: dict[str, list[Task]] = {key: [] for key, _ in STAGES}
    for task in tasks:
        grouped.setdefault(task.status, []).append(task)
    return [
        {"key": key, "label": label, "tasks": grouped[key]}
        for key, label in STAGES
    ]


def _sort_side_list(tasks: list[Task]) -> list[Task]:
    ordered = sorted(
        tasks,
        key=lambda task: task.created_at or datetime.min,
        reverse=True,
    )
    ordered.sort(
        key=lambda task: {"high": 0, "medium": 1, "low": 2}.get(
            task.priority, 3
        )
    )
    return ordered


def _task_dialog(raw: str | None) -> str | None:
    if not raw:
        return None
    try:
        task_id = int(raw)
    except (TypeError, ValueError):
        return None
    if db.session.get(Task, task_id) is None:
        return None
    return f"task-{task_id}"


def _parse_month(raw: str | None) -> date:
    today = _today_wib()
    if raw:
        match = MONTH_PATTERN.match(raw.strip())
        if match:
            year, month = int(match.group(1)), int(match.group(2))
            if 1 <= month <= 12 and MIN_MONTH <= (year, month) <= MAX_MONTH:
                return date(year, month, 1)
    return date(today.year, today.month, 1)


def _shift_month(month_start: date, delta: int) -> date:
    month_index = month_start.year * 12 + (month_start.month - 1) + delta
    year, month_zero = divmod(month_index, 12)
    if year < 1 or year > 9999:
        return month_start
    return date(year, month_zero + 1, 1)


def _calendar_data(
    month_start: date, tasks: list[Task]
) -> dict[str, Any]:
    today = _today_wib()
    weeks_dates = calendar.Calendar(firstweekday=0).monthdatescalendar(
        month_start.year, month_start.month
    )
    first_day = weeks_dates[0][0]
    last_day = weeks_dates[-1][-1]

    by_date: dict[date, list[Task]] = {}
    for task in tasks:
        if (
            task.due_date is not None
            and first_day <= task.due_date <= last_day
        ):
            by_date.setdefault(task.due_date, []).append(task)
    for day_tasks in by_date.values():
        day_tasks[:] = _sort_side_list(day_tasks)

    weeks = []
    for week in weeks_dates:
        days = []
        for day in week:
            days.append(
                {
                    "date": day,
                    "in_month": (
                        day.year == month_start.year
                        and day.month == month_start.month
                    ),
                    "is_today": day == today,
                    "tasks": by_date.get(day, []),
                }
            )
        weeks.append(days)

    undated = _sort_side_list(
        [task for task in tasks if task.due_date is None]
    )
    return {
        "month": month_start,
        "month_label": (
            f"{MONTHS_LONG[month_start.month - 1]} {month_start.year}"
        ),
        "prev_month": _shift_month(month_start, -1).strftime("%Y-%m"),
        "next_month": _shift_month(month_start, 1).strftime("%Y-%m"),
        "weeks": weeks,
        "undated": undated,
    }


def _gantt_data(
    tasks: list[Task], today: date
) -> dict[str, Any]:
    undated = _sort_side_list(
        [task for task in tasks if task.due_date is None]
    )

    bars: list[tuple[Task, date, date]] = []
    bar_starts: list[date] = []
    bar_ends: list[date] = []
    for task in tasks:
        if task.due_date is None:
            continue
        created_date = (
            _to_wib(task.created_at).date()
            if task.created_at is not None
            else today
        )
        if task.due_date < created_date:
            bar_start = task.due_date
            bar_end = task.due_date
        else:
            bar_start = created_date
            bar_end = task.due_date
        bars.append((task, bar_start, bar_end))
        bar_starts.append(bar_start)
        bar_ends.append(bar_end)

    range_start = min(
        bar_starts + [_safe_date_offset(today, -2)]
    )
    range_end = max(
        bar_ends + [_safe_date_offset(today, 12)]
    )

    max_days = 45
    if (range_end - range_start).days + 1 > max_days:
        capped_end = _safe_date_offset(range_start, max_days - 1)
        if capped_end < today:
            # Keep today visible when a very old bar would push the window past it.
            range_end = _safe_date_offset(today, 12)
            range_start = _safe_date_offset(range_end, -(max_days - 1))
        else:
            range_end = capped_end

    day_count = (range_end - range_start).days + 1
    days = [
        range_start + timedelta(days=offset) for offset in range(day_count)
    ]
    today_index = days.index(today) if today in days else None

    rows = []
    for task, bar_start, bar_end in bars:
        start_index = (bar_start - range_start).days
        end_index = (bar_end - range_start).days
        if end_index < 0:
            start_index = 0
            span = 1
        elif start_index >= day_count:
            start_index = day_count - 1
            span = 1
        else:
            start_index = max(0, start_index)
            end_index = min(day_count - 1, end_index)
            span = max(1, end_index - start_index + 1)
        rows.append(
            {"task": task, "start_index": start_index, "span": span}
        )

    return {
        "days": days,
        "today_index": today_index,
        "rows": rows,
        "undated": undated,
    }


def _render_app(
    *,
    view: str = "board",
    priority: str = "all",
    month_start: date | None = None,
    open_dialog: str | None = None,
    errors: Mapping[str, str] | None = None,
    form: Mapping[str, Any] | None = None,
    code: int = 200,
):
    today = _today_wib()
    if month_start is None:
        month_start = date(today.year, today.month, 1)
    tasks = _fetch_tasks(priority)

    body = render_template(
        "app.html",
        view=view,
        priority=priority,
        counts=_counts(),
        columns=_board_columns_from(tasks),
        tasks=tasks,
        calendar=_calendar_data(month_start, tasks),
        gantt=_gantt_data(tasks, today),
        timelines={task.id: timeline(task) for task in tasks},
        errors=dict(errors or {}),
        form=dict(form or {}),
        open_dialog=open_dialog,
        today=today,
        stages=STAGES,
        stage_labels=STAGE_LABELS,
    )
    return body, code


@bp.get("/")
def index():
    view = _parse_view(request.args.get("view"))
    priority = _filter_lenient(request.args.get("priority"), PRIORITIES)
    month_start = _parse_month(request.args.get("month"))
    open_dialog = _task_dialog(request.args.get("task"))
    return _render_app(
        view=view,
        priority=priority,
        month_start=month_start,
        open_dialog=open_dialog,
    )


@bp.post("/tasks")
def create_task_form():
    payload = request.form.to_dict(flat=True)
    try:
        values = _validate_task(payload, partial=False)
    except ValidationError as error:
        return _render_app(
            view=_parse_view(request.args.get("view")),
            priority=_filter_lenient(
                request.args.get("priority"), PRIORITIES
            ),
            errors=error.fields,
            form=payload,
            open_dialog="create",
            code=400,
        )

    task = Task(**values)
    db.session.add(task)
    db.session.flush()
    _add_event(task, None, task.status, task.created_at)
    db.session.commit()
    flash("Tugas berhasil ditambahkan.", "success")
    return redirect(_next_url())


@bp.get("/tasks/<int:task_id>")
def task_detail(task_id: int):
    return redirect(url_for("main.index", task=task_id))


@bp.get("/tasks/<int:task_id>/edit")
def edit_task_page(task_id: int):
    return redirect(url_for("main.index", task=task_id))


@bp.post("/tasks/<int:task_id>/edit")
def update_task_form(task_id: int):
    task = _get_task_or_404(task_id)
    payload = request.form.to_dict(flat=True)
    payload.setdefault("title", "")
    try:
        values = _validate_task(payload, partial=True)
    except ValidationError as error:
        return _render_app(
            view=_parse_view(request.args.get("view")),
            priority=_filter_lenient(
                request.args.get("priority"), PRIORITIES
            ),
            errors=error.fields,
            form=payload,
            open_dialog=f"task-{task.id}",
            code=400,
        )

    new_status = values.pop("status", None)
    for field, value in values.items():
        setattr(task, field, value)
    if new_status is not None:
        _move_task(task, new_status)
    db.session.commit()
    flash("Perubahan berhasil disimpan.", "success")
    return redirect(_next_url())


@bp.post("/tasks/<int:task_id>/move")
def move_task(task_id: int):
    task = _get_task_or_404(task_id)
    status = (request.form.get("status") or "").strip()
    if status not in STAGE_LABELS:
        flash("Status tidak valid.", "error")
    else:
        _move_task(task, status)
        db.session.commit()
        flash(f"Dipindah ke {STAGE_LABELS[status]}.", "success")
    return redirect(_next_url())


@bp.post("/tasks/<int:task_id>/delete")
def delete_task_form(task_id: int):
    task = _get_task_or_404(task_id)
    db.session.delete(task)
    db.session.commit()
    flash("Tugas berhasil dihapus.", "success")
    return redirect(_next_url())


@bp.get("/calendar")
def calendar_view():
    params: dict[str, str] = {"view": "calendar"}
    month = request.args.get("month")
    if month:
        params["month"] = month
    return redirect(url_for("main.index", **params))


@bp.get("/api/tasks")
def api_list_tasks():
    status = _filter_strict(request.args.get("status"), "status", STATUS_KEYS)
    priority = _filter_strict(
        request.args.get("priority"), "priority", PRIORITIES
    )
    tasks = db.session.scalars(_task_query(status, priority)).all()
    return jsonify(
        {"data": [task.to_dict() for task in tasks], "count": len(tasks)}
    )


@bp.post("/api/tasks")
def api_create_task():
    payload = _read_json_payload()
    values = _validate_task(payload, partial=False)

    task = Task(**values)
    db.session.add(task)
    db.session.flush()
    _add_event(task, None, task.status, task.created_at)
    db.session.commit()

    response = jsonify({"data": task.to_dict()})
    response.status_code = 201
    response.headers["Location"] = url_for(
        "main.api_get_task", task_id=task.id
    )
    return response


@bp.get("/api/tasks/<int:task_id>")
def api_get_task(task_id: int):
    task = _get_task_or_404(task_id)
    return jsonify({"data": task.to_dict()})


@bp.put("/api/tasks/<int:task_id>")
def api_update_task(task_id: int):
    task = _get_task_or_404(task_id)
    payload = _read_json_payload()
    values = _validate_task(payload, partial=True)

    new_status = values.pop("status", None)
    for field, value in values.items():
        setattr(task, field, value)
    if new_status is not None:
        _move_task(task, new_status)
    db.session.commit()
    return jsonify({"data": task.to_dict()})


@bp.post("/api/tasks/<int:task_id>/move")
def api_move_task(task_id: int):
    task = _get_task_or_404(task_id)
    payload = _read_json_payload()
    raw_status = payload.get("status")
    status = (
        raw_status.strip().lower()
        if isinstance(raw_status, str) and raw_status.strip()
        else ""
    )
    if status not in STAGE_LABELS:
        raise ValidationError("Data tidak valid.", {"status": _status_error()})

    _move_task(task, status)
    db.session.commit()
    return jsonify({"data": task.to_dict()})


@bp.get("/api/tasks/<int:task_id>/history")
def api_task_history(task_id: int):
    task = _get_task_or_404(task_id)
    events = _task_events(task)
    return jsonify(
        {
            "data": [
                {
                    "from_status": event.from_status,
                    "to_status": event.to_status,
                    "to_label": STAGE_LABELS.get(
                        event.to_status, event.to_status
                    ),
                    "created_at": _iso_z(event.created_at),
                }
                for event in events
            ]
        }
    )


@bp.delete("/api/tasks/<int:task_id>")
def api_delete_task(task_id: int):
    task = _get_task_or_404(task_id)
    db.session.delete(task)
    db.session.commit()
    return jsonify({"message": "Tugas dihapus"})


def _is_api_request() -> bool:
    path = request.path
    return path == "/api" or path.startswith("/api/")


def _json_error(
    message: str, code: int, fields: Mapping[str, str] | None = None
):
    return (
        jsonify({"error": {"message": message, "fields": dict(fields or {})}}),
        code,
    )


def _register_error_handlers(app: Flask) -> None:
    @app.errorhandler(ValidationError)
    def handle_validation_error(error: ValidationError):
        return _json_error(error.message, 400, error.fields)

    @app.errorhandler(400)
    def handle_bad_request(error):
        if _is_api_request():
            return _json_error("Permintaan tidak valid.", 400)
        return (
            render_template(
                "error.html", code=400, message="Permintaan tidak valid."
            ),
            400,
        )

    @app.errorhandler(404)
    def handle_not_found(error):
        if _is_api_request():
            return _json_error("Tidak ditemukan.", 404)
        return (
            render_template(
                "error.html", code=404, message="Halaman tidak ditemukan."
            ),
            404,
        )

    @app.errorhandler(405)
    def handle_method_not_allowed(error):
        if _is_api_request():
            return _json_error("Metode tidak diizinkan.", 405)
        return (
            render_template(
                "error.html", code=405, message="Metode tidak diizinkan."
            ),
            405,
        )

    @app.errorhandler(500)
    def handle_server_error(error):
        try:
            db.session.rollback()
        except Exception:  # pragma: no cover - defensive rollback
            pass
        if _is_api_request():
            return _json_error("Terjadi kesalahan pada server.", 500)
        return (
            render_template(
                "error.html",
                code=500,
                message="Terjadi kesalahan pada server.",
            ),
            500,
        )


def create_app(config: Mapping[str, Any] | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_mapping(
        SECRET_KEY=os.getenv("SECRET_KEY", "dev-secret-key"),
        SQLALCHEMY_DATABASE_URI=os.getenv(
            "DATABASE_URL", DEFAULT_DATABASE_URL
        ),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )
    if config:
        app.config.update(config)
    app.json.sort_keys = False

    db.init_app(app)
    app.register_blueprint(bp)
    _register_error_handlers(app)

    app.jinja_env.filters["wib"] = format_wib
    app.jinja_env.filters["tanggal"] = format_tanggal
    app.jinja_env.filters["durasi"] = format_durasi

    @app.context_processor
    def inject_stages():
        return {"stages": STAGES, "stage_labels": STAGE_LABELS}

    @app.cli.command("seed")
    @click.option(
        "--reset",
        is_flag=True,
        help="Delete all existing tasks before seeding.",
    )
    def seed_command(reset: bool) -> None:
        count = db.session.scalar(db.select(db.func.count(Task.id))) or 0
        if count and not reset:
            click.echo(
                "Seed refused: tasks already exist. "
                "Use --reset to replace them."
            )
            return
        if reset:
            db.session.execute(db.delete(TaskEvent))
            db.session.execute(db.delete(Task))
            db.session.commit()

        now = _utcnow()
        today = _today_wib()
        for spec in SEED_TASKS:
            history = spec["history"]
            created_at = now - timedelta(days=history[0][1])
            due_date = (
                today + timedelta(days=spec["due_in_days"])
                if spec["due_in_days"] is not None
                else None
            )
            task = Task(
                title=spec["title"],
                description=spec["description"],
                due_date=due_date,
                priority=spec["priority"],
                status=spec["status"],
                created_at=created_at,
                updated_at=now - timedelta(days=history[-1][1]),
            )
            db.session.add(task)
            db.session.flush()
            previous_status = None
            for to_status, days_ago in history:
                _add_event(
                    task,
                    previous_status,
                    to_status,
                    now - timedelta(days=days_ago),
                )
                previous_status = to_status
        db.session.commit()
        click.echo(f"Seeded {len(SEED_TASKS)} tasks.")

    with app.app_context():
        db.create_all()

    return app


app = create_app()
