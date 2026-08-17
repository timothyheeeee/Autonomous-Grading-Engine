import time
from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from app.main import app


def _rubric_bytes() -> bytes:
    image = Image.new("RGB", (720, 480), "white")
    draw = ImageDraw.Draw(image)
    draw.text((20, 20), "Group Project Rubric 1-5 Collaboration Communication", fill="black")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def main() -> None:
    from app.config import BACKEND_ROOT

    csv_bytes = (BACKEND_ROOT / "data" / "sample_peer_reviews.csv").read_bytes()
    with TestClient(app) as client:
        boot = client.get("/api/auth/bootstrap")
        print("bootstrap", boot.status_code, boot.json()["role"])
        token = boot.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        denied = client.post(
            "/api/pipeline/run",
            files={"csv_file": ("a.csv", csv_bytes, "text/csv"), "rubric_image": ("r.png", _rubric_bytes(), "image/png")},
        )
        print("no jwt", denied.status_code)
        started = client.post(
            "/api/pipeline/run",
            headers=headers,
            files={"csv_file": ("a.csv", csv_bytes, "text/csv"), "rubric_image": ("r.png", _rubric_bytes(), "image/png")},
        )
        print("run", started.status_code, started.json()["status"], started.json()["thread_id"])
        thread = started.json()["thread_id"]
        payload = None
        for _ in range(40):
            payload = client.get(f"/api/pipeline/{thread}", headers=headers).json()
            if payload["status"] in {"pending_review", "error", "published"}:
                break
            time.sleep(0.15)
        print("poll", payload["status"], "roster", payload.get("dynamic_roster"), "node", payload.get("current_node"))
        if payload["status"] == "pending_review":
            approved = client.post(f"/api/pipeline/{thread}/approve", headers=headers, json={"approved": True})
            print("approve", approved.status_code, approved.json()["status"])


if __name__ == "__main__":
    main()
