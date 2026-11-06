"""Интеграционные тесты: HTTP-запросы через TestClient к приложению с настоящей БД."""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.helpers import created

RESOURCES = ["users", "projects", "labels", "tasks", "comments"]


@pytest.mark.parametrize("resource", RESOURCES)
class TestCommonBehaviour:
    def test_empty_list(self, client: TestClient, resource: str) -> None:
        response = client.get(f"/v1/{resource}")
        assert response.status_code == 200
        assert response.json() == []

    def test_missing_record_is_404(self, client: TestClient, resource: str) -> None:
        assert client.get(f"/v1/{resource}/999").status_code == 404
        assert client.patch(f"/v1/{resource}/999", json={}).status_code == 404
        assert client.delete(f"/v1/{resource}/999").status_code == 404

    @pytest.mark.parametrize("bad_id", ["abc", "0", "-1", "2147483648"])
    def test_invalid_id_is_422(self, client: TestClient, resource: str, bad_id: str) -> None:
        assert client.get(f"/v1/{resource}/{bad_id}").status_code == 422

    def test_invalid_body_is_422(self, client: TestClient, resource: str) -> None:
        assert client.post(f"/v1/{resource}", json={}).status_code == 422


class TestUsers:
    def test_crud(self, client: TestClient) -> None:
        user = created(
            client.post("/v1/users", json={"email": "a@example.com", "display_name": "A"})
        )
        assert user["role"] == "operator"
        assert set(user) == {"id", "email", "display_name", "role", "created_at"}

        assert client.get(f"/v1/users/{user['id']}").json() == user
        assert client.get("/v1/users").json() == [user]

        response = client.patch(f"/v1/users/{user['id']}", json={"role": "admin"})
        assert response.status_code == 200
        assert response.json()["role"] == "admin"
        assert response.json()["email"] == "a@example.com"

        response = client.delete(f"/v1/users/{user['id']}")
        assert response.status_code == 204
        assert response.content == b""
        assert client.get(f"/v1/users/{user['id']}").status_code == 404

    def test_duplicate_email_is_409(self, client: TestClient, user: dict[str, Any]) -> None:
        response = client.post("/v1/users", json={"email": user["email"], "display_name": "X"})
        assert response.status_code == 409
        assert "already exists" in response.json()["detail"]

    def test_patch_to_duplicate_email_is_409(
        self, client: TestClient, user: dict[str, Any]
    ) -> None:
        other = created(
            client.post("/v1/users", json={"email": "b@example.com", "display_name": "B"})
        )
        response = client.patch(f"/v1/users/{other['id']}", json={"email": user["email"]})
        assert response.status_code == 409

    def test_service_fields_are_rejected(self, client: TestClient) -> None:
        response = client.post(
            "/v1/users", json={"id": 10, "email": "a@example.com", "display_name": "A"}
        )
        assert response.status_code == 422

    def test_author_with_comments_cannot_be_deleted(
        self, client: TestClient, user: dict[str, Any], comment: dict[str, Any]
    ) -> None:
        response = client.delete(f"/v1/users/{user['id']}")
        assert response.status_code == 409
        assert client.get(f"/v1/users/{user['id']}").status_code == 200

    def test_deleting_assignee_clears_task(
        self, client: TestClient, user: dict[str, Any], task: dict[str, Any]
    ) -> None:
        assert client.delete(f"/v1/users/{user['id']}").status_code == 204
        assert client.get(f"/v1/tasks/{task['id']}").json()["assignee_id"] is None


class TestProjects:
    def test_crud(self, client: TestClient) -> None:
        project = created(client.post("/v1/projects", json={"name": "P", "description": "D"}))
        assert client.get(f"/v1/projects/{project['id']}").json() == project
        assert client.get("/v1/projects").json() == [project]

        response = client.patch(f"/v1/projects/{project['id']}", json={"description": None})
        assert response.status_code == 200
        assert response.json()["description"] is None
        assert response.json()["name"] == "P"

        assert client.delete(f"/v1/projects/{project['id']}").status_code == 204
        assert client.get(f"/v1/projects/{project['id']}").status_code == 404

    def test_patch_null_name_is_422(self, client: TestClient, project: dict[str, Any]) -> None:
        assert client.patch(f"/v1/projects/{project['id']}", json={"name": None}).status_code == 422

    def test_delete_cascades(
        self,
        client: TestClient,
        project: dict[str, Any],
        task: dict[str, Any],
        comment: dict[str, Any],
    ) -> None:
        assert client.delete(f"/v1/projects/{project['id']}").status_code == 204
        assert client.get(f"/v1/tasks/{task['id']}").status_code == 404
        assert client.get(f"/v1/comments/{comment['id']}").status_code == 404


class TestLabels:
    def test_crud(self, client: TestClient) -> None:
        label = created(client.post("/v1/labels", json={"name": "feature"}))
        assert label["color"] == "#6b7280"
        assert client.get(f"/v1/labels/{label['id']}").json() == label
        assert client.get("/v1/labels").json() == [label]

        response = client.patch(f"/v1/labels/{label['id']}", json={"color": "#22c55e"})
        assert response.status_code == 200
        assert response.json()["color"] == "#22c55e"

        assert client.delete(f"/v1/labels/{label['id']}").status_code == 204
        assert client.get(f"/v1/labels/{label['id']}").status_code == 404

    def test_duplicate_name_is_409(self, client: TestClient, label: dict[str, Any]) -> None:
        assert client.post("/v1/labels", json={"name": label["name"]}).status_code == 409

    def test_invalid_color_is_422(self, client: TestClient) -> None:
        assert client.post("/v1/labels", json={"name": "x", "color": "blue"}).status_code == 422

    def test_deleting_label_clears_task(
        self, client: TestClient, label: dict[str, Any], task: dict[str, Any]
    ) -> None:
        assert client.delete(f"/v1/labels/{label['id']}").status_code == 204
        assert client.get(f"/v1/tasks/{task['id']}").json()["label_id"] is None


class TestTasks:
    def test_crud(self, client: TestClient, project: dict[str, Any]) -> None:
        task = created(client.post("/v1/tasks", json={"project_id": project["id"], "title": "T"}))
        assert (task["status"], task["priority"]) == ("open", "medium")
        assert client.get(f"/v1/tasks/{task['id']}").json() == task
        assert client.get("/v1/tasks").json() == [task]

        response = client.patch(f"/v1/tasks/{task['id']}", json={"status": "done"})
        assert response.status_code == 200
        updated = response.json()
        assert updated["status"] == "done"
        assert updated["title"] == "T"
        assert updated["updated_at"] > task["updated_at"]
        assert updated["created_at"] == task["created_at"]

        assert client.delete(f"/v1/tasks/{task['id']}").status_code == 204
        assert client.get(f"/v1/tasks/{task['id']}").status_code == 404

    @pytest.mark.parametrize("field", ["project_id", "assignee_id", "label_id"])
    def test_unknown_reference_is_409(
        self, client: TestClient, project: dict[str, Any], field: str
    ) -> None:
        payload = {"project_id": project["id"], "title": "T", field: 999}
        response = client.post("/v1/tasks", json=payload)
        assert response.status_code == 409
        assert "does not exist" in response.json()["detail"]

    def test_patch_unknown_project_is_409(self, client: TestClient, task: dict[str, Any]) -> None:
        assert client.patch(f"/v1/tasks/{task['id']}", json={"project_id": 999}).status_code == 409

    def test_patch_can_clear_assignee(self, client: TestClient, task: dict[str, Any]) -> None:
        response = client.patch(f"/v1/tasks/{task['id']}", json={"assignee_id": None})
        assert response.json()["assignee_id"] is None

    @pytest.mark.parametrize(
        "payload", [{"status": "closed"}, {"priority": "urgent"}, {"title": None}, {"id": 5}]
    )
    def test_invalid_patch_is_422(
        self, client: TestClient, task: dict[str, Any], payload: dict[str, Any]
    ) -> None:
        assert client.patch(f"/v1/tasks/{task['id']}", json=payload).status_code == 422

    def test_filters(self, client: TestClient, project: dict[str, Any]) -> None:
        other = created(client.post("/v1/projects", json={"name": "Other"}))
        open_task = created(
            client.post("/v1/tasks", json={"project_id": project["id"], "title": "A"})
        )
        done_task = created(
            client.post(
                "/v1/tasks", json={"project_id": project["id"], "title": "B", "status": "done"}
            )
        )
        foreign = created(client.post("/v1/tasks", json={"project_id": other["id"], "title": "C"}))

        def ids(query: str) -> list[int]:
            response = client.get(f"/v1/tasks{query}")
            assert response.status_code == 200
            return [t["id"] for t in response.json()]

        assert ids("") == [open_task["id"], done_task["id"], foreign["id"]]
        assert ids(f"?project_id={project['id']}") == [open_task["id"], done_task["id"]]
        assert ids("?status=open") == [open_task["id"], foreign["id"]]
        assert ids(f"?project_id={project['id']}&status=open") == [open_task["id"]]
        assert ids(f"?project_id={other['id']}&status=done") == []

    @pytest.mark.parametrize("query", ["?status=closed", "?project_id=abc", "?project_id=0"])
    def test_invalid_filter_is_422(self, client: TestClient, query: str) -> None:
        assert client.get(f"/v1/tasks{query}").status_code == 422


class TestComments:
    def test_crud(self, client: TestClient, task: dict[str, Any], user: dict[str, Any]) -> None:
        comment = created(
            client.post(
                "/v1/comments", json={"task_id": task["id"], "author_id": user["id"], "body": "Hi"}
            )
        )
        assert client.get(f"/v1/comments/{comment['id']}").json() == comment
        assert client.get("/v1/comments").json() == [comment]

        response = client.patch(f"/v1/comments/{comment['id']}", json={"body": "Edited"})
        assert response.status_code == 200
        assert response.json()["body"] == "Edited"

        assert client.delete(f"/v1/comments/{comment['id']}").status_code == 204
        assert client.get(f"/v1/comments/{comment['id']}").status_code == 404

    @pytest.mark.parametrize("field", ["task_id", "author_id"])
    def test_unknown_reference_is_409(
        self, client: TestClient, task: dict[str, Any], user: dict[str, Any], field: str
    ) -> None:
        payload = {"task_id": task["id"], "author_id": user["id"], "body": "x", field: 999}
        assert client.post("/v1/comments", json=payload).status_code == 409

    def test_blank_body_is_422(
        self, client: TestClient, task: dict[str, Any], user: dict[str, Any]
    ) -> None:
        payload = {"task_id": task["id"], "author_id": user["id"], "body": "   "}
        assert client.post("/v1/comments", json=payload).status_code == 422

    def test_filter_by_task(
        self,
        client: TestClient,
        project: dict[str, Any],
        task: dict[str, Any],
        user: dict[str, Any],
        comment: dict[str, Any],
    ) -> None:
        other_task = created(
            client.post("/v1/tasks", json={"project_id": project["id"], "title": "Other"})
        )
        created(
            client.post(
                "/v1/comments",
                json={"task_id": other_task["id"], "author_id": user["id"], "body": "x"},
            )
        )
        response = client.get(f"/v1/comments?task_id={task['id']}")
        assert response.status_code == 200
        assert [c["id"] for c in response.json()] == [comment["id"]]
        assert len(client.get("/v1/comments").json()) == 2

    def test_task_delete_cascades(
        self, client: TestClient, task: dict[str, Any], comment: dict[str, Any]
    ) -> None:
        assert client.delete(f"/v1/tasks/{task['id']}").status_code == 204
        assert client.get(f"/v1/comments/{comment['id']}").status_code == 404
