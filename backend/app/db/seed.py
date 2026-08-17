from sqlalchemy.orm import Session


def seed_if_empty(db: Session) -> None:
    """System starts empty — no roster and no published percentages."""
    _ = db
    return None
