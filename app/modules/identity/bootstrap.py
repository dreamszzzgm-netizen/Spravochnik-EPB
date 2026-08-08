import argparse
import getpass
import sys

from sqlalchemy import select

from app.database.session import get_session_factory
from app.modules.identity.models import Employee, User
from app.modules.identity.security import hash_password


def bootstrap_superuser(username: str, full_name: str, password: str) -> None:
    normalized = username.strip().lower()
    with get_session_factory()() as db:
        if db.scalar(select(User).where(User.username == normalized)):
            raise RuntimeError(f"User {normalized!r} already exists")
        employee = Employee(full_name=full_name)
        db.add(employee)
        db.flush()
        user = User(
            employee_id=employee.id,
            username=normalized,
            password_hash=hash_password(password),
            is_active=True,
            is_superuser=True,
            must_change_password=False,
        )
        db.add(user)
        db.commit()


def run() -> None:
    parser = argparse.ArgumentParser(description="Create the initial Spravoshnik EPB superuser")
    parser.add_argument("--username", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--password")
    args = parser.parse_args()
    password = args.password or getpass.getpass("Password (min 12 chars): ")
    try:
        bootstrap_superuser(args.username, args.name, password)
    except Exception as exc:
        print(f"Bootstrap failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    print("Superuser created")


if __name__ == "__main__":
    run()
