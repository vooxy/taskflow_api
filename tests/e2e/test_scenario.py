"""E2E-тесты: настоящий сервер Uvicorn запускается отдельным процессом,
тест обращается к нему по HTTP, как обычный клиент (сценарий из раздела «Как проверить работу»)."""

import os
import socket
import subprocess
import sys
import time
from collections.abc import Callable, Iterator
from pathlib import Path

import httpx
import pytest

from tests.conftest import TEST_DATABASE_URL

ROOT = Path(__file__).resolve().parents[2]


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port: int = sock.getsockname()[1]
        return port


@pytest.fixture
def server(clean_db: None) -> Iterator[Callable[[], str]]:
    """Возвращает функцию (пере)запуска сервера; сервер останавливается после теста."""
    port = free_port()
    processes: list[subprocess.Popen[bytes]] = []

    def stop() -> None:
        while processes:
            process = processes.pop()
            process.terminate()
            process.wait(timeout=10)

    def start() -> str:
        stop()
        env = {**os.environ, "DATABASE_URL": str(TEST_DATABASE_URL), "LOG_LEVEL": "WARNING"}
        process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(port)],
            cwd=ROOT,
            env=env,
        )
        processes.append(process)
        base_url = f"http://127.0.0.1:{port}"
        for _ in range(100):
            try:
                if httpx.get(f"{base_url}/health").status_code == 200:
                    return base_url
            except httpx.TransportError:
                pass
            time.sleep(0.1)
        raise RuntimeError("Server did not start")

    yield start
    stop()


def test_full_scenario(server: Callable[[], str]) -> None:
    api = httpx.Client(base_url=server())

    # 0. сервер работает и видит БД, документация открывается
    assert api.get("/health").json() == {"status": "ok", "database": "up"}
    assert api.get("/docs").status_code == 200

    # 1. пользователь, проект, метка
    user = api.post("/v1/users", json={"email": "karim@example.com", "display_name": "Karim"})
    keeper = api.post("/v1/projects", json={"name": "Stays after restart"})
    project = api.post("/v1/projects", json={"name": "Backend course"})
    label = api.post("/v1/labels", json={"name": "bug", "color": "#ef4444"})
    assert [r.status_code for r in (user, keeper, project, label)] == [201] * 4
    user_id, project_id = user.json()["id"], project.json()["id"]

    # 2. задача со ссылками на них
    task = api.post(
        "/v1/tasks",
        json={
            "project_id": project_id,
            "assignee_id": user_id,
            "label_id": label.json()["id"],
            "title": "Write tests",
            "priority": "high",
        },
    )
    assert task.status_code == 201
    task_id = task.json()["id"]

    # 3. комментарий к задаче
    comment = api.post(
        "/v1/comments", json={"task_id": task_id, "author_id": user_id, "body": "On it"}
    )
    assert comment.status_code == 201

    # 4. задача и списки с фильтрами
    assert api.get(f"/v1/tasks/{task_id}").json()["title"] == "Write tests"
    open_tasks = api.get("/v1/tasks", params={"project_id": project_id, "status": "open"}).json()
    assert [t["id"] for t in open_tasks] == [task_id]
    comments = api.get("/v1/comments", params={"task_id": task_id}).json()
    assert [c["id"] for c in comments] == [comment.json()["id"]]

    # 5. статус -> done
    done = api.patch(f"/v1/tasks/{task_id}", json={"status": "done"})
    assert done.status_code == 200 and done.json()["status"] == "done"
    assert api.get("/v1/tasks", params={"status": "open"}).json() == []

    # ошибки клиента
    assert (
        api.post("/v1/users", json={"email": "karim@example.com", "display_name": "X"}).status_code
        == 409
    )
    assert api.post("/v1/tasks", json={"project_id": 999, "title": "X"}).status_code == 409
    assert api.post("/v1/tasks", json={"project_id": project_id}).status_code == 422
    assert api.get("/v1/tasks/999").status_code == 404

    # 6. удаление проекта удаляет задачи и комментарии
    assert api.delete(f"/v1/projects/{project_id}").status_code == 204
    assert api.get(f"/v1/tasks/{task_id}").status_code == 404
    assert api.get(f"/v1/comments/{comment.json()['id']}").status_code == 404

    # 7. перезапуск сервера — остальные данные сохранились
    api = httpx.Client(base_url=server())
    assert [p["name"] for p in api.get("/v1/projects").json()] == ["Stays after restart"]
    assert api.get(f"/v1/users/{user_id}").status_code == 200
    assert len(api.get("/v1/labels").json()) == 1
