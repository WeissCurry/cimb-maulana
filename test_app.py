"""Backend tests using in-memory SQLite and stubbed templates."""

import os
from datetime import date, datetime, timedelta, timezone

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["SECRET_KEY"] = "test-secret"

import pytest
from flask import template_rendered
from jinja2 import DictLoader

import app as app_module
from app import (
    PRIORITIES,
    SEED_TASKS,
    STAGE_LABELS,
    STAGES,
    STATUS_KEYS,
    Task,
    TaskEvent,
    create_app,
    db,
    timeline,
)

TEMPLATE_NAMES = (
    "app.html",
    "error.html",
)


@pytest.fixture()
def app():
    application = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SECRET_KEY": "test-secret",
        }
    )
    application.jinja_env.loader = DictLoader(
        {name: "" for name in TEMPLATE_NAMES}
    )
    with application.app_context():
        db.drop_all()
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def rendered(app):
    records = []

    def record(sender, template, context, **extra):
        records.append((template.name, context))

    template_rendered.connect(record, app)
    yield records
    template_rendered.disconnect(record, app)


def _create(client, **fields):
    payload = {"title": "Tugas contoh"}
    payload.update(fields)
    response = client.post("/api/tasks", json=payload)
    assert response.status_code == 201, response.get_json()
    return response.get_json()["data"]


def _history(client, task_id):
    response = client.get(f"/api/tasks/{task_id}/history")
    assert response.status_code == 200, response.get_json()
    return response.get_json()["data"]


def _event_count():
    return db.session.scalar(db.select(db.func.count(TaskEvent.id))) or 0


def _flashes(client):
    with client.session_transaction() as session:
        return [tuple(item) for item in session.get("_flashes", [])]


def _ctx(rendered, name):
    matches = [
        context
        for template_name, context in rendered
        if template_name == name
    ]
    assert matches, f"{name} tidak dirender"
    return matches[-1]


def test_stages_and_context_processor(client, rendered):
    assert STAGES == [
        ("todo", "Belum Mulai"),
        ("in_progress", "Dikerjakan"),
        ("ready", "Siap Dicek"),
        ("review", "Review"),
        ("done", "Selesai"),
    ]
    assert STAGE_LABELS["in_progress"] == "Dikerjakan"

    response = client.get("/")
    assert response.status_code == 200
    context = _ctx(rendered, "app.html")
    assert context["stages"] == STAGES
    assert context["stage_labels"] == STAGE_LABELS


def test_task_to_dict_status_label_and_z_timestamps(app):
    task = Task(title="Cek model", due_date=date(2000, 1, 1))
    db.session.add(task)
    db.session.commit()

    data = task.to_dict()
    assert data["status"] == "todo"
    assert data["status_label"] == "Belum Mulai"
    assert data["is_overdue"] is True
    assert data["created_at"].endswith("Z")
    assert data["updated_at"].endswith("Z")
    assert data["due_date"] == "2000-01-01"


@pytest.mark.parametrize("status", ["todo", "in_progress", "ready", "review"])
def test_is_overdue_uses_status_not_done(app, status):
    task = Task(title="Telat", due_date=date(2000, 1, 1), status=status)
    assert task.is_overdue is True


def test_is_overdue_done_task_is_false(app):
    task = Task(title="Selesai", due_date=date(2000, 1, 1), status="done")
    assert task.is_overdue is False

    future = Task(title="Nanti", due_date=date(2999, 1, 1), status="todo")
    assert future.is_overdue is False


def test_jinja_filters(app):
    wib = app.jinja_env.filters["wib"]
    tanggal = app.jinja_env.filters["tanggal"]
    durasi = app.jinja_env.filters["durasi"]

    assert wib(datetime(2026, 11, 6, 7, 30)) == "6 Nov 2026, 14:30"
    assert wib(None) == ""
    assert tanggal(date(2026, 11, 10)) == "10 Nov 2026"
    assert tanggal(None) == ""
    assert durasi(3060) == "2 hari 3 jam"
    assert durasi(45) == "45 menit"
    assert durasi(90) == "1 jam 30 menit"
    assert durasi(1440) == "1 hari"
    assert durasi(0) == "0 menit"


def test_api_create_defaults_and_initial_event(client):
    created = _create(client, title="  Beli kopi  ")
    assert created["title"] == "Beli kopi"
    assert created["status"] == "todo"
    assert created["status_label"] == "Belum Mulai"
    assert created["priority"] == "medium"
    assert created["created_at"].endswith("Z")

    events = db.session.scalars(db.select(TaskEvent)).all()
    assert len(events) == 1
    assert events[0].from_status is None
    assert events[0].to_status == "todo"

    history = _history(client, created["id"])
    assert len(history) == 1
    assert history[0]["from_status"] is None
    assert history[0]["to_status"] == "todo"
    assert history[0]["to_label"] == "Belum Mulai"
    assert history[0]["created_at"].endswith("Z")


def test_api_create_with_status_writes_event(client):
    created = _create(client, title="Siap dicek", status="ready")
    assert created["status_label"] == "Siap Dicek"

    events = db.session.scalars(db.select(TaskEvent)).all()
    assert len(events) == 1
    assert events[0].from_status is None
    assert events[0].to_status == "ready"


@pytest.mark.parametrize(
    ("payload", "field"),
    [
        ({}, "title"),
        ({"title": "   "}, "title"),
        ({"title": "x" * 201}, "title"),
        ({"title": 123}, "title"),
        ({"title": "ok", "description": "x" * 2001}, "description"),
        ({"title": "ok", "due_date": "10-11-2026"}, "due_date"),
        ({"title": "ok", "due_date": "2026-02-30"}, "due_date"),
        ({"title": "ok", "priority": "urgent"}, "priority"),
        ({"title": "ok", "status": "selesai"}, "status"),
        ({"title": "ok", "status": None}, "status"),
    ],
)
def test_create_validation(client, payload, field):
    response = client.post("/api/tasks", json=payload)
    assert response.status_code == 400
    assert response.get_json()["error"]["fields"][field]
    assert _event_count() == 0


def test_create_bad_json(client):
    response = client.post(
        "/api/tasks", data='{"title": ', content_type="application/json"
    )
    assert response.status_code == 400
    assert "json" in response.get_json()["error"]["message"].lower()


@pytest.mark.parametrize(
    ("data", "content_type"),
    [
        ("[]", "application/json"),
        ("title=Halo", "text/plain"),
        ("", "application/json"),
    ],
)
def test_create_invalid_body_shape(client, data, content_type):
    response = client.post(
        "/api/tasks", data=data, content_type=content_type
    )
    assert response.status_code == 400
    assert response.get_json()["error"]["fields"] == {}


def test_html_create_writes_event(client):
    response = client.post(
        "/tasks",
        data={
            "title": "  Tugas HTML  ",
            "description": "Catatan",
            "due_date": "2030-02-03",
            "priority": "high",
            "status": "ready",
        },
    )
    assert response.status_code == 302
    assert response.headers["Location"] == "/"
    assert ("success", "Tugas berhasil ditambahkan.") in _flashes(client)

    task = db.session.scalars(db.select(Task)).one()
    assert task.title == "Tugas HTML"
    assert task.status == "ready"
    assert task.due_date == date(2030, 2, 3)

    events = db.session.scalars(db.select(TaskEvent)).all()
    assert len(events) == 1
    assert events[0].from_status is None
    assert events[0].to_status == "ready"


def test_html_create_invalid_rerenders_app(client, rendered):
    response = client.post(
        "/tasks",
        data={
            "title": "",
            "description": "",
            "due_date": "salah",
            "priority": "high",
        },
    )
    assert response.status_code == 400
    context = _ctx(rendered, "app.html")
    assert "title" in context["errors"]
    assert "due_date" in context["errors"]
    assert context["form"]["title"] == ""
    assert context["open_dialog"] == "create"
    assert _event_count() == 0


def test_api_list_filters_and_sort(client):
    a = _create(client, title="A", priority="high", due_date="2026-12-10")
    b = _create(client, title="B", priority="low")
    c = _create(
        client,
        title="C",
        status="in_progress",
        priority="medium",
        due_date="2026-12-05",
    )
    d = _create(
        client,
        title="D",
        status="done",
        priority="high",
        due_date="2026-12-01",
    )
    e = _create(
        client,
        title="E",
        status="ready",
        priority="medium",
        due_date="2026-12-10",
    )

    body = client.get("/api/tasks").get_json()
    assert body["count"] == 5
    assert [item["title"] for item in body["data"]] == ["A", "B", "C", "E", "D"]

    body = client.get("/api/tasks?status=todo").get_json()
    assert [item["id"] for item in body["data"]] == [a["id"], b["id"]]

    body = client.get("/api/tasks?status=in_progress").get_json()
    assert [item["id"] for item in body["data"]] == [c["id"]]

    body = client.get("/api/tasks?priority=high").get_json()
    assert [item["id"] for item in body["data"]] == [a["id"], d["id"]]

    body = client.get("/api/tasks?status=review").get_json()
    assert body["count"] == 0
    assert body["data"] == []


@pytest.mark.parametrize(
    ("query", "field"),
    [
        ("status=selesai", "status"),
        ("priority=urgent", "priority"),
    ],
)
def test_api_list_invalid_filter(client, query, field):
    response = client.get(f"/api/tasks?{query}")
    assert response.status_code == 400
    assert response.get_json()["error"]["fields"][field]


def test_api_move_creates_event(client):
    created = _create(client, title="Pindah")

    response = client.post(
        f"/api/tasks/{created['id']}/move",
        json={"status": "in_progress"},
    )
    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["status"] == "in_progress"
    assert data["status_label"] == "Dikerjakan"

    history = _history(client, created["id"])
    assert [(item["from_status"], item["to_status"]) for item in history] == [
        (None, "todo"),
        ("todo", "in_progress"),
    ]
    assert history[1]["to_label"] == "Dikerjakan"


def test_api_move_same_status_writes_no_event(client):
    created = _create(client, title="Tetap")
    response = client.post(
        f"/api/tasks/{created['id']}/move", json={"status": "todo"}
    )
    assert response.status_code == 200
    assert _event_count() == 1
    assert len(_history(client, created["id"])) == 1


@pytest.mark.parametrize(
    "payload",
    [{}, {"status": "bogus"}, {"status": None}, {"status": 123}],
)
def test_api_move_validation(client, payload):
    created = _create(client, title="Validasi pindah")
    response = client.post(
        f"/api/tasks/{created['id']}/move", json=payload
    )
    assert response.status_code == 400
    assert response.get_json()["error"]["fields"]["status"]
    assert _event_count() == 1


def test_api_move_bad_json_and_missing_task(client):
    created = _create(client, title="Bad JSON")
    response = client.post(
        f"/api/tasks/{created['id']}/move",
        data="{",
        content_type="application/json",
    )
    assert response.status_code == 400

    response = client.post(
        "/api/tasks/999999/move", json={"status": "done"}
    )
    assert response.status_code == 404
    assert response.is_json


def test_history_order_oldest_first(client):
    created = _create(client, title="Riwayat")
    task_id = created["id"]
    for status in ("in_progress", "ready", "done"):
        response = client.post(
            f"/api/tasks/{task_id}/move", json={"status": status}
        )
        assert response.status_code == 200

    history = _history(client, task_id)
    assert [(item["from_status"], item["to_status"]) for item in history] == [
        (None, "todo"),
        ("todo", "in_progress"),
        ("in_progress", "ready"),
        ("ready", "done"),
    ]
    assert [item["to_label"] for item in history] == [
        "Belum Mulai",
        "Dikerjakan",
        "Siap Dicek",
        "Selesai",
    ]
    assert all(item["created_at"].endswith("Z") for item in history)
    timestamps = [
        datetime.fromisoformat(item["created_at"].replace("Z", "+00:00"))
        for item in history
    ]
    assert timestamps == sorted(timestamps)


def test_api_history_missing_task(client):
    response = client.get("/api/tasks/999999/history")
    assert response.status_code == 404
    assert response.is_json


def test_html_move_valid_writes_event(client):
    created = _create(client, title="Pindah HTML")
    response = client.post(
        f"/tasks/{created['id']}/move",
        data={"status": "ready", "next": "/?priority=high"},
    )
    assert response.status_code == 302
    assert response.headers["Location"] == "/?priority=high"

    task = db.session.get(Task, created["id"])
    assert task.status == "ready"
    assert _event_count() == 2
    assert ("success", "Dipindah ke Siap Dicek.") in _flashes(client)


def test_html_move_invalid_flashes_error(client):
    created = _create(client, title="Pindah salah")
    response = client.post(
        f"/tasks/{created['id']}/move",
        data={"status": "bogus", "next": "/calendar"},
    )
    assert response.status_code == 302
    assert response.headers["Location"] == "/calendar"

    task = db.session.get(Task, created["id"])
    assert task.status == "todo"
    assert _event_count() == 1
    assert ("error", "Status tidak valid.") in _flashes(client)


def test_html_move_same_status_writes_no_event(client):
    created = _create(client, title="Tetap HTML")
    response = client.post(
        f"/tasks/{created['id']}/move", data={"status": "todo"}
    )
    assert response.status_code == 302
    assert _event_count() == 1


@pytest.mark.parametrize(
    "target",
    [
        "/\\evil.example",
        "/%5Cevil.example",
        "/%5cevil.example",
        "//evil.example",
        "http://evil.example",
        "/ok\\evil",
        "/ok\x00evil",
        "/ok\tevil",
        "/ok\nevil",
        "\\evil.example",
        "/%5c",
    ],
)
def test_next_url_rejects_unsafe_targets(client, target):
    created = _create(client, title="Next tidak aman")
    response = client.post(
        f"/tasks/{created['id']}/move",
        data={"status": "ready", "next": target},
    )
    assert response.status_code == 302
    assert response.headers["Location"] == "/"


@pytest.mark.parametrize(
    "target",
    [
        "/?view=calendar&month=2026-11",
        "/?priority=high",
        "/?task=1",
        "/calendar",
    ],
)
def test_next_url_accepts_safe_targets(client, target):
    created = _create(client, title="Next aman")
    response = client.post(
        f"/tasks/{created['id']}/move",
        data={"status": "ready", "next": target},
    )
    assert response.status_code == 302
    assert response.headers["Location"] == target


def test_html_edit_status_change_writes_event(client):
    created = _create(client, title="Edit")
    response = client.post(
        f"/tasks/{created['id']}/edit",
        data={
            "title": "Edit baru",
            "description": "",
            "due_date": "",
            "priority": "high",
            "status": "review",
        },
    )
    assert response.status_code == 302
    assert response.headers["Location"] == "/"
    assert ("success", "Perubahan berhasil disimpan.") in _flashes(client)

    task = db.session.get(Task, created["id"])
    assert task.title == "Edit baru"
    assert task.status == "review"
    assert _event_count() == 2


def test_html_edit_same_status_and_missing_status(client):
    created = _create(client, title="Awal", status="review")

    response = client.post(
        f"/tasks/{created['id']}/edit",
        data={
            "title": "Tanpa status",
            "description": "",
            "due_date": "",
            "priority": "medium",
        },
    )
    assert response.status_code == 302
    task = db.session.get(Task, created["id"])
    assert task.title == "Tanpa status"
    assert task.status == "review"
    assert _event_count() == 1

    response = client.post(
        f"/tasks/{created['id']}/edit",
        data={
            "title": "Status sama",
            "description": "",
            "due_date": "",
            "priority": "medium",
            "status": "review",
        },
    )
    assert response.status_code == 302
    assert _event_count() == 1


def test_html_edit_invalid_status_rerenders(client, rendered):
    created = _create(client, title="Tetap")
    response = client.post(
        f"/tasks/{created['id']}/edit",
        data={
            "title": "Berubah",
            "description": "",
            "due_date": "",
            "priority": "medium",
            "status": "bogus",
        },
    )
    assert response.status_code == 400
    context = _ctx(rendered, "app.html")
    assert context["errors"]["status"]
    assert context["open_dialog"] == f"task-{created['id']}"

    task = db.session.get(Task, created["id"])
    assert task.title == "Tetap"
    assert task.status == "todo"
    assert _event_count() == 1


def test_api_put_status_event_and_same_status_no_event(client):
    created = _create(client, title="PUT")
    task_id = created["id"]

    response = client.put(
        f"/api/tasks/{task_id}", json={"status": "in_progress"}
    )
    assert response.status_code == 200
    assert response.get_json()["data"]["status"] == "in_progress"
    assert _event_count() == 2

    response = client.put(
        f"/api/tasks/{task_id}", json={"status": "in_progress"}
    )
    assert response.status_code == 200
    assert _event_count() == 2

    response = client.put(f"/api/tasks/{task_id}", json={"title": "Baru"})
    assert response.status_code == 200
    assert _event_count() == 2


def test_api_update_partial_validation_and_404(client):
    created = _create(client, title="Awal", priority="low")
    task_id = created["id"]

    response = client.put(
        f"/api/tasks/{task_id}", json={"description": "baru"}
    )
    data = response.get_json()["data"]
    assert data["title"] == "Awal"
    assert data["description"] == "baru"
    assert data["priority"] == "low"

    response = client.put(f"/api/tasks/{task_id}", json={"title": ""})
    assert response.status_code == 400
    assert response.get_json()["error"]["fields"]["title"]

    response = client.put(
        f"/api/tasks/{task_id}", json={"status": "selesai"}
    )
    assert response.status_code == 400
    assert response.get_json()["error"]["fields"]["status"]

    response = client.put("/api/tasks/999999", json={"title": "Hilang"})
    assert response.status_code == 404


def test_api_update_bad_json(client):
    created = _create(client, title="Bad update")
    response = client.put(
        f"/api/tasks/{created['id']}",
        data="{bukan json",
        content_type="application/json",
    )
    assert response.status_code == 400
    assert response.get_json()["error"]["message"]


def test_delete_cascades_events(client):
    created = _create(client, title="Hapus")
    client.post(
        f"/api/tasks/{created['id']}/move", json={"status": "ready"}
    )
    assert _event_count() == 2

    response = client.delete(f"/api/tasks/{created['id']}")
    assert response.status_code == 200
    assert response.get_json() == {"message": "Tugas dihapus"}
    assert _event_count() == 0

    response = client.get(f"/api/tasks/{created['id']}")
    assert response.status_code == 404


def test_html_delete(client):
    created = _create(client, title="Hapus HTML")
    response = client.post(
        f"/tasks/{created['id']}/delete", data={"next": "/calendar"}
    )
    assert response.status_code == 302
    assert response.headers["Location"] == "/calendar"
    assert ("success", "Tugas berhasil dihapus.") in _flashes(client)
    assert _event_count() == 0


def test_timeline_durations_and_wib(app):
    task = Task(title="Linimasa", created_at=datetime(2026, 11, 6, 0, 0))
    db.session.add(task)
    db.session.flush()
    db.session.add_all(
        [
            TaskEvent(
                task_id=task.id,
                from_status=None,
                to_status="todo",
                created_at=datetime(2026, 11, 6, 0, 0),
            ),
            TaskEvent(
                task_id=task.id,
                from_status="todo",
                to_status="in_progress",
                created_at=datetime(2026, 11, 6, 2, 0),
            ),
            TaskEvent(
                task_id=task.id,
                from_status="in_progress",
                to_status="done",
                created_at=datetime(2026, 11, 7, 5, 30),
            ),
        ]
    )
    db.session.commit()

    now = datetime(2026, 11, 7, 7, 0, tzinfo=timezone.utc)
    items = timeline(task, now=now)

    assert [item["status"] for item in items] == [
        "todo",
        "in_progress",
        "done",
    ]
    assert [item["label"] for item in items] == [
        "Belum Mulai",
        "Dikerjakan",
        "Selesai",
    ]
    assert [item["duration_minutes"] for item in items] == [120, 1650, 90]

    first = items[0]
    assert first["entered_at"].utcoffset() == timedelta(hours=7)
    assert first["entered_at"].hour == 7
    assert first["left_at"].hour == 9
    assert items[-1]["left_at"] is None


def test_task_dialog_context_and_timeline(client, rendered):
    created = _create(client, title="Detail")
    client.post(
        f"/api/tasks/{created['id']}/move", json={"status": "ready"}
    )

    response = client.get(f"/?task={created['id']}")
    assert response.status_code == 200
    context = _ctx(rendered, "app.html")
    assert context["open_dialog"] == f"task-{created['id']}"
    assert [item["status"] for item in context["timelines"][created["id"]]] == [
        "todo",
        "ready",
    ]
    assert context["today"] == app_module._today_wib()


def test_task_dialog_ignores_missing_or_invalid_id(client, rendered):
    client.get("/?task=999999")
    context = _ctx(rendered, "app.html")
    assert context["open_dialog"] is None

    client.get("/?task=bukan-angka")
    context = _ctx(rendered, "app.html")
    assert context["open_dialog"] is None


def test_board_columns_counts_and_priority(client, rendered):
    a = _create(client, title="A", priority="high", due_date="2026-12-10")
    b = _create(client, title="B", priority="medium", due_date="2026-12-10")
    c = _create(client, title="C", priority="low")
    d = _create(client, title="D", priority="high", due_date="2026-12-20")
    e = _create(
        client,
        title="E",
        status="in_progress",
        priority="medium",
        due_date="2026-12-05",
    )
    f = _create(
        client,
        title="F",
        status="done",
        priority="high",
        due_date="2026-12-01",
    )

    response = client.get("/")
    assert response.status_code == 200
    context = _ctx(rendered, "app.html")
    assert context["view"] == "board"
    assert [column["key"] for column in context["columns"]] == [
        "todo",
        "in_progress",
        "ready",
        "review",
        "done",
    ]
    assert [column["label"] for column in context["columns"]] == [
        "Belum Mulai",
        "Dikerjakan",
        "Siap Dicek",
        "Review",
        "Selesai",
    ]
    by_key = {column["key"]: column["tasks"] for column in context["columns"]}
    assert [task.id for task in by_key["todo"]] == [
        a["id"],
        b["id"],
        d["id"],
        c["id"],
    ]
    assert [task.id for task in by_key["in_progress"]] == [e["id"]]
    assert by_key["ready"] == []
    assert by_key["review"] == []
    assert [task.id for task in by_key["done"]] == [f["id"]]
    assert context["counts"] == {
        "all": 6,
        "todo": 4,
        "in_progress": 1,
        "ready": 0,
        "review": 0,
        "done": 1,
    }
    assert context["priority"] == "all"
    assert context["today"] == app_module._today_wib()
    assert [task.id for task in context["tasks"]] == [
        a["id"],
        b["id"],
        d["id"],
        c["id"],
        e["id"],
        f["id"],
    ]

    client.get("/?priority=high")
    context = _ctx(rendered, "app.html")
    by_key = {column["key"]: column["tasks"] for column in context["columns"]}
    assert [task.id for task in by_key["todo"]] == [a["id"], d["id"]]
    assert [task.id for task in by_key["done"]] == [f["id"]]
    assert [task.id for task in context["tasks"]] == [
        a["id"],
        d["id"],
        f["id"],
    ]
    assert context["counts"]["all"] == 6
    assert context["priority"] == "high"


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("", "board"),
        ("?view=board", "board"),
        ("?view=list", "list"),
        ("?view=calendar", "calendar"),
        ("?view=gantt", "gantt"),
        ("?view=ngawur", "board"),
    ],
)
def test_view_param_and_fallback(client, rendered, query, expected):
    response = client.get(f"/{query}")
    assert response.status_code == 200
    context = _ctx(rendered, "app.html")
    assert context["view"] == expected


def test_board_invalid_priority_falls_back(client, rendered):
    _create(client, title="A", priority="high")
    response = client.get("/?priority=urgent")
    assert response.status_code == 200
    context = _ctx(rendered, "app.html")
    assert context["priority"] == "all"


def test_task_get_routes_redirect_to_app_dialog(client):
    created = _create(client, title="Tautan lama")

    response = client.get(f"/tasks/{created['id']}")
    assert response.status_code == 302
    assert response.headers["Location"] == f"/?task={created['id']}"

    response = client.get(f"/tasks/{created['id']}/edit")
    assert response.status_code == 302
    assert response.headers["Location"] == f"/?task={created['id']}"

    response = client.get("/tasks/999999")
    assert response.status_code == 302
    assert response.headers["Location"] == "/?task=999999"


def test_calendar_route_redirects_with_month(client):
    response = client.get("/calendar?month=2026-02")
    assert response.status_code == 302
    assert response.headers["Location"] == "/?view=calendar&month=2026-02"

    response = client.get("/calendar")
    assert response.status_code == 302
    assert response.headers["Location"] == "/?view=calendar"


def _calendar_days(calendar_data):
    return [day for week in calendar_data["weeks"] for day in week]


def test_calendar_weeks_monday_first_and_month_boundaries(
    client, rendered, monkeypatch
):
    monkeypatch.setattr(
        app_module, "_today_wib", lambda: date(2026, 2, 15)
    )

    jan26 = _create(client, title="Jan", due_date="2026-01-26")
    feb10_high = _create(
        client, title="Feb tinggi", due_date="2026-02-10", priority="high"
    )
    feb10_low = _create(
        client, title="Feb rendah", due_date="2026-02-10", priority="low"
    )
    feb28 = _create(client, title="Feb akhir", due_date="2026-02-28")
    mar1 = _create(client, title="Mar", due_date="2026-03-01")
    undated = _create(client, title="Tanpa tenggat")

    response = client.get("/?view=calendar&month=2026-02")
    assert response.status_code == 200
    context = _ctx(rendered, "app.html")
    assert context["view"] == "calendar"
    calendar_data = context["calendar"]

    assert calendar_data["month"] == date(2026, 2, 1)
    assert calendar_data["month_label"] == "February 2026"
    assert calendar_data["prev_month"] == "2026-01"
    assert calendar_data["next_month"] == "2026-03"
    assert context["today"] == date(2026, 2, 15)

    weeks = calendar_data["weeks"]
    assert len(weeks) == 5
    assert all(len(week) == 7 for week in weeks)
    assert all(week[0]["date"].weekday() == 0 for week in weeks)
    assert weeks[0][0]["date"] == date(2026, 1, 26)
    assert weeks[0][0]["in_month"] is False
    assert weeks[0][6]["date"] == date(2026, 2, 1)
    assert weeks[0][6]["in_month"] is True
    assert weeks[-1][-1]["date"] == date(2026, 3, 1)
    assert weeks[-1][-1]["in_month"] is False

    by_day = {day["date"]: day for day in _calendar_days(calendar_data)}
    assert [task.id for task in by_day[date(2026, 1, 26)]["tasks"]] == [
        jan26["id"]
    ]
    assert [task.id for task in by_day[date(2026, 2, 10)]["tasks"]] == [
        feb10_high["id"],
        feb10_low["id"],
    ]
    assert [task.id for task in by_day[date(2026, 2, 28)]["tasks"]] == [
        feb28["id"]
    ]
    assert [task.id for task in by_day[date(2026, 3, 1)]["tasks"]] == [
        mar1["id"]
    ]
    assert by_day[date(2026, 2, 15)]["is_today"] is True
    assert by_day[date(2026, 2, 10)]["is_today"] is False
    assert [task.id for task in calendar_data["undated"]] == [undated["id"]]


@pytest.mark.parametrize("raw_month", ["2026-13", "ngawur", "2026-1", "0000-01"])
def test_calendar_invalid_month_falls_back(
    client, rendered, monkeypatch, raw_month
):
    monkeypatch.setattr(
        app_module, "_today_wib", lambda: date(2026, 11, 6)
    )
    response = client.get(f"/?view=calendar&month={raw_month}")
    assert response.status_code == 200
    calendar_data = _ctx(rendered, "app.html")["calendar"]
    assert calendar_data["month"] == date(2026, 11, 1)
    assert calendar_data["month_label"] == "November 2026"
    assert calendar_data["prev_month"] == "2026-10"
    assert calendar_data["next_month"] == "2026-12"


@pytest.mark.parametrize("raw_month", ["0001-01", "9999-12"])
def test_calendar_out_of_range_months_fall_back(
    client, rendered, monkeypatch, raw_month
):
    monkeypatch.setattr(
        app_module, "_today_wib", lambda: date(2026, 11, 6)
    )
    response = client.get(f"/?view=calendar&month={raw_month}")
    assert response.status_code == 200
    calendar_data = _ctx(rendered, "app.html")["calendar"]
    assert calendar_data["month"] == date(2026, 11, 1)
    assert calendar_data["prev_month"] == "2026-10"
    assert calendar_data["next_month"] == "2026-12"


@pytest.mark.parametrize(
    ("raw_month", "expected", "prev_month", "next_month"),
    [
        ("0001-02", date(1, 2, 1), "0001-01", "0001-03"),
        ("9999-11", date(9999, 11, 1), "9999-10", "9999-12"),
    ],
)
def test_calendar_supported_edge_months_render(
    client, rendered, raw_month, expected, prev_month, next_month
):
    response = client.get(f"/?view=calendar&month={raw_month}")
    assert response.status_code == 200
    calendar_data = _ctx(rendered, "app.html")["calendar"]
    assert calendar_data["month"] == expected
    assert calendar_data["prev_month"] == prev_month
    assert calendar_data["next_month"] == next_month
    days = _calendar_days(calendar_data)
    assert days
    assert all(date.min <= day["date"] <= date.max for day in days)


def test_gantt_range_bars_today_index_and_undated(
    client, rendered, monkeypatch
):
    monkeypatch.setattr(
        app_module, "_today_wib", lambda: date(2026, 11, 6)
    )
    long_bar = Task(
        title="Panjang",
        created_at=datetime(2026, 11, 1, 0, 0),
        due_date=date(2026, 11, 10),
    )
    reversed_bar = Task(
        title="Terbalik",
        created_at=datetime(2026, 11, 20, 0, 0),
        due_date=date(2026, 11, 1),
    )
    undated = Task(
        title="Tanpa tenggat", created_at=datetime(2026, 11, 2, 0, 0)
    )
    db.session.add_all([long_bar, reversed_bar, undated])
    db.session.commit()

    client.get("/")
    gantt = _ctx(rendered, "app.html")["gantt"]

    assert gantt["days"][0] == date(2026, 11, 1)
    assert gantt["days"][-1] == date(2026, 11, 18)
    assert len(gantt["days"]) == 18
    assert gantt["today_index"] == 5
    assert gantt["days"][gantt["today_index"]] == date(2026, 11, 6)

    rows = {row["task"].id: row for row in gantt["rows"]}
    assert len(rows) == 2
    assert rows[long_bar.id]["start_index"] == 0
    assert rows[long_bar.id]["span"] == 10
    assert rows[reversed_bar.id]["start_index"] == 0
    assert rows[reversed_bar.id]["span"] == 1
    assert [task.id for task in gantt["undated"]] == [undated.id]


def test_gantt_caps_to_45_days_and_clips_bars(
    client, rendered, monkeypatch
):
    today = date(2026, 11, 6)
    monkeypatch.setattr(app_module, "_today_wib", lambda: today)

    old = Task(
        title="Lama",
        created_at=datetime(2020, 1, 1, 0, 0),
        due_date=date(2020, 1, 10),
    )
    future = Task(
        title="Masa depan",
        created_at=datetime(2030, 1, 1, 0, 0),
        due_date=date(2030, 1, 5),
    )
    spanning = Task(
        title="Menjangkau",
        created_at=datetime(2020, 1, 1, 0, 0),
        due_date=date(2030, 1, 1),
    )
    db.session.add_all([old, future, spanning])
    db.session.commit()

    client.get("/")
    gantt = _ctx(rendered, "app.html")["gantt"]

    assert len(gantt["days"]) == 45
    assert gantt["today_index"] is not None
    assert gantt["days"][gantt["today_index"]] == today
    assert gantt["days"][0] == date(2026, 10, 5)
    assert gantt["days"][-1] == date(2026, 11, 18)

    rows = {row["task"].id: row for row in gantt["rows"]}
    for row in rows.values():
        assert 0 <= row["start_index"] < 45
        assert row["span"] >= 1
        assert row["start_index"] + row["span"] <= 45

    assert rows[old.id]["start_index"] == 0
    assert rows[old.id]["span"] == 1
    assert rows[future.id]["start_index"] == 44
    assert rows[future.id]["span"] == 1
    assert rows[spanning.id]["start_index"] == 0
    assert rows[spanning.id]["span"] == 45


def test_gantt_extreme_due_dates_do_not_overflow(
    client, rendered, monkeypatch
):
    today = date(2026, 11, 6)
    monkeypatch.setattr(app_module, "_today_wib", lambda: today)

    earliest = _create(client, title="Min", due_date="0001-01-01")
    latest = _create(client, title="Max", due_date="9999-12-31")

    response = client.get("/?view=gantt")
    assert response.status_code == 200
    gantt = _ctx(rendered, "app.html")["gantt"]

    assert len(gantt["days"]) == 45
    assert gantt["today_index"] is not None
    assert gantt["days"][gantt["today_index"]] == today
    assert gantt["days"][0] >= date.min
    assert gantt["days"][-1] <= date.max

    rows = {row["task"].id: row for row in gantt["rows"]}
    assert set(rows) == {earliest["id"], latest["id"]}
    for row in rows.values():
        assert 0 <= row["start_index"] < 45
        assert row["span"] >= 1
        assert row["start_index"] + row["span"] <= 45
    assert rows[earliest["id"]]["start_index"] == 0
    assert rows[earliest["id"]]["span"] == 1


def test_seed_command_populates_tasks(app):
    runner = app.test_cli_runner()
    result = runner.invoke(args=["seed"])
    assert result.exit_code == 0, result.output

    tasks = db.session.scalars(db.select(Task)).all()
    assert len(tasks) == 14 == len(SEED_TASKS)
    assert {task.status for task in tasks} == set(STATUS_KEYS)
    assert {task.priority for task in tasks} == set(PRIORITIES)
    assert sum(1 for task in tasks if task.due_date is None) == 2

    today = app_module._today_wib()
    due_dates = [task.due_date for task in tasks if task.due_date]
    assert any(due < today for due in due_dates)
    assert any(today <= due <= today + timedelta(days=6) for due in due_dates)
    assert any(today < due <= today + timedelta(days=21) for due in due_dates)

    assert _event_count() == sum(
        len(spec["history"]) for spec in SEED_TASKS
    )
    for task in tasks:
        events = sorted(task.events, key=lambda event: event.created_at)
        assert events[0].from_status is None
        assert events[0].created_at == task.created_at
        assert events[-1].to_status == task.status
        assert task.updated_at == events[-1].created_at
        assert all(
            events[index].created_at < events[index + 1].created_at
            for index in range(len(events) - 1)
        )
        items = timeline(task)
        assert items[-1]["status"] == task.status
        assert all(item["duration_minutes"] >= 0 for item in items)


def test_seed_refuses_without_reset(app):
    runner = app.test_cli_runner()
    assert runner.invoke(args=["seed"]).exit_code == 0
    task_ids = set(db.session.scalars(db.select(Task.id)).all())
    event_count = _event_count()

    result = runner.invoke(args=["seed"])
    assert result.exit_code == 0
    assert "--reset" in result.output
    assert set(db.session.scalars(db.select(Task.id)).all()) == task_ids
    assert _event_count() == event_count


def test_seed_reset_replaces_tasks(app):
    runner = app.test_cli_runner()
    assert runner.invoke(args=["seed"]).exit_code == 0

    result = runner.invoke(args=["seed", "--reset"])
    assert result.exit_code == 0, result.output
    tasks = db.session.scalars(db.select(Task)).all()
    assert len(tasks) == len(SEED_TASKS)
    assert _event_count() == sum(
        len(spec["history"]) for spec in SEED_TASKS
    )


def test_api_unknown_path_and_method(client):
    response = client.get("/api/tidak-ada")
    assert response.status_code == 404
    assert response.is_json

    created = _create(client, title="405")
    response = client.patch(f"/api/tasks/{created['id']}")
    assert response.status_code == 405
    assert response.is_json
    assert response.get_json()["error"]["message"]


def test_html_500_renders_error_context(app, client, rendered):
    def boom():
        raise RuntimeError("boom")

    app.add_url_rule("/ledakan", "ledakan", boom)
    app.config["PROPAGATE_EXCEPTIONS"] = False
    app.logger.disabled = True

    response = client.get("/ledakan")
    assert response.status_code == 500
    context = _ctx(rendered, "error.html")
    assert context["code"] == 500


def test_api_500_returns_json(app, client):
    def boom():
        raise RuntimeError("boom")

    app.add_url_rule("/api/ledakan", "api_ledakan", boom)
    app.config["PROPAGATE_EXCEPTIONS"] = False
    app.logger.disabled = True

    response = client.get("/api/ledakan")
    assert response.status_code == 500
    assert response.is_json
    assert response.get_json()["error"]["message"]
