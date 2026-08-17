import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.session import get_db
from app.modules.identity.audit import write_audit
from app.modules.identity.dependencies import (
    get_current_user,
    get_session_token,
    require_permission,
)
from app.modules.identity.models import (
    Employee,
    EmployeeFunctionRole,
    EmployeeFunctionRoleAssignment,
    Permission,
    Role,
    RolePermission,
    User,
    UserRoleAssignment,
)
from app.modules.identity.repository import get_user_permission_codes
from app.modules.identity.schemas import (
    AdminPasswordResetRequest,
    ChangePasswordRequest,
    CurrentUserResponse,
    EmployeeCreate,
    EmployeeResponse,
    FunctionRoleAssignmentCreate,
    LoginRequest,
    LoginResponse,
    PermissionGrant,
    RoleAssignmentCreate,
    RoleCreate,
    UserCreate,
    UserResponse,
)
from app.modules.identity.security import hash_password
from app.modules.identity.service import AccountLockedError, AuthenticationError, AuthService

router = APIRouter(prefix="/api", tags=["identity"])


@router.post("/auth/login", response_model=LoginResponse)
def login(
    payload: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)
):
    settings = get_settings()
    try:
        result = AuthService(settings).login(
            db,
            username=payload.username,
            password=payload.password,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("User-Agent"),
        )
    except AccountLockedError as exc:
        raise HTTPException(status_code=status.HTTP_423_LOCKED, detail=str(exc)) from exc
    except AuthenticationError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    response.set_cookie(
        settings.session_cookie_name,
        result.token,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="strict",
        max_age=settings.session_absolute_timeout_minutes * 60,
        path="/",
    )
    return LoginResponse(must_change_password=result.user.must_change_password)


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    response: Response,
    token: str = Depends(get_session_token),
    db: Session = Depends(get_db),
):
    settings = get_settings()
    AuthService(settings).logout(
        db, token=token, ip_address=request.client.host if request.client else None
    )
    response.delete_cookie(settings.session_cookie_name, path="/")
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/auth/me", response_model=CurrentUserResponse)
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.is_superuser:
        permissions = db.scalars(select(Permission.code).order_by(Permission.code)).all()
    else:
        permissions = get_user_permission_codes(db, user.id)
    return CurrentUserResponse(
        id=user.id,
        employee_id=user.employee_id,
        username=user.username,
        is_superuser=user.is_superuser,
        must_change_password=user.must_change_password,
        permissions=list(permissions),
    )


@router.post("/auth/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    payload: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        AuthService(get_settings()).change_password(
            db,
            user=user,
            current_password=payload.current_password,
            new_password=payload.new_password,
        )
    except AuthenticationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/employees", response_model=list[EmployeeResponse])
def list_employees(
    _actor: User = Depends(require_permission("employees.view")),
    db: Session = Depends(get_db),
):
    employees = (
        db.scalars(
            select(Employee)
            .where(Employee.deleted_at.is_(None))
            .order_by(Employee.full_name.asc(), Employee.id.asc())
        ).all()
    )
    return list(employees)


@router.post(
    "/admin/employees", response_model=EmployeeResponse, status_code=status.HTTP_201_CREATED
)
def create_employee(
    payload: EmployeeCreate,
    actor: User = Depends(require_permission("employees.create")),
    db: Session = Depends(get_db),
):
    employee = Employee(**payload.model_dump())
    db.add(employee)
    db.flush()
    write_audit(
        db,
        action="employee.create",
        summary="Employee created",
        result="success",
        user_id=actor.id,
        entity_type="employee",
        entity_id=employee.id,
    )
    db.commit()
    db.refresh(employee)
    return employee


@router.post("/admin/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    actor: User = Depends(require_permission("users.create")),
    db: Session = Depends(get_db),
):
    employee = db.get(Employee, payload.employee_id)
    if employee is None or employee.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Employee not found")
    user = User(
        employee_id=payload.employee_id,
        username=payload.username.strip().lower(),
        password_hash=hash_password(payload.password),
        is_active=payload.is_active,
        is_superuser=payload.is_superuser,
        must_change_password=payload.must_change_password,
    )
    db.add(user)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="Username or employee already has a user"
        ) from exc
    write_audit(
        db,
        action="user.create",
        summary="User created",
        result="success",
        user_id=actor.id,
        entity_type="user",
        entity_id=user.id,
    )
    db.commit()
    db.refresh(user)
    return user


@router.post("/admin/users/{user_id}/roles", status_code=status.HTTP_201_CREATED)
def assign_role(
    user_id: uuid.UUID,
    payload: RoleAssignmentCreate,
    actor: User = Depends(require_permission("users.manage_roles")),
    db: Session = Depends(get_db),
):
    if db.get(User, user_id) is None:
        raise HTTPException(status_code=404, detail="User not found")
    assignment = UserRoleAssignment(
        user_id=user_id,
        role_id=payload.role_id,
        scope_type=payload.scope_type,
        scope_config=payload.scope_config,
        assigned_by=actor.id,
    )
    db.add(assignment)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="Active role assignment already exists or role is invalid"
        ) from exc
    write_audit(
        db,
        action="user.role_assigned",
        summary="Authorization role assigned",
        result="success",
        user_id=actor.id,
        entity_type="user",
        entity_id=user_id,
        metadata={"scope_type": payload.scope_type.value},
    )
    db.commit()
    return {"id": assignment.id}


@router.post("/admin/users/{user_id}/revoke-sessions")
def revoke_sessions(
    user_id: uuid.UUID,
    actor: User = Depends(require_permission("users.revoke_sessions")),
    db: Session = Depends(get_db),
):
    if db.get(User, user_id) is None:
        raise HTTPException(status_code=404, detail="User not found")
    count = AuthService(get_settings()).revoke_all_sessions(
        db, user_id=user_id, initiated_by=actor.id
    )
    return {"revoked": count}


@router.post("/admin/users/{user_id}/reset-password", status_code=status.HTTP_204_NO_CONTENT)
def reset_password(
    user_id: uuid.UUID,
    payload: AdminPasswordResetRequest,
    actor: User = Depends(require_permission("users.reset_password")),
    db: Session = Depends(get_db),
):
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")
    AuthService(get_settings()).administrative_password_reset(
        db,
        user=target,
        temporary_password=payload.temporary_password,
        initiated_by=actor.id,
        reason=payload.reason,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/admin/roles", status_code=status.HTTP_201_CREATED)
def create_role(
    payload: RoleCreate,
    actor: User = Depends(require_permission("users.manage_roles")),
    db: Session = Depends(get_db),
):
    role = Role(code=payload.code, name=payload.name, is_system=payload.is_system)
    db.add(role)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Role code already exists") from exc
    write_audit(
        db,
        action="role.create",
        summary="Authorization role created",
        result="success",
        user_id=actor.id,
        entity_type="role",
        entity_id=role.id,
    )
    db.commit()
    return {"id": role.id, "code": role.code, "name": role.name}


@router.get("/admin/permissions")
def list_permissions(
    _actor: User = Depends(require_permission("users.manage_roles")),
    db: Session = Depends(get_db),
):
    items = db.scalars(select(Permission).order_by(Permission.code)).all()
    return [{"id": item.id, "code": item.code, "name": item.name} for item in items]


@router.post("/admin/roles/{role_id}/permissions", status_code=status.HTTP_201_CREATED)
def grant_permission(
    role_id: uuid.UUID,
    payload: PermissionGrant,
    actor: User = Depends(require_permission("users.manage_roles")),
    db: Session = Depends(get_db),
):
    role = db.get(Role, role_id)
    permission = db.scalar(select(Permission).where(Permission.code == payload.permission_code))
    if role is None or permission is None:
        raise HTTPException(status_code=404, detail="Role or permission not found")
    db.add(RolePermission(role_id=role.id, permission_id=permission.id))
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Permission already granted") from exc
    write_audit(
        db,
        action="role.permission_granted",
        summary="Permission granted to role",
        result="success",
        user_id=actor.id,
        entity_type="role",
        entity_id=role.id,
        metadata={"permission_code": permission.code},
    )
    db.commit()
    return {"role_id": role.id, "permission_code": permission.code}


@router.delete(
    "/admin/users/{user_id}/roles/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT
)
def revoke_role_assignment(
    user_id: uuid.UUID,
    assignment_id: uuid.UUID,
    actor: User = Depends(require_permission("users.manage_roles")),
    db: Session = Depends(get_db),
):
    assignment = db.get(UserRoleAssignment, assignment_id)
    if assignment is None or assignment.user_id != user_id or assignment.revoked_at is not None:
        raise HTTPException(status_code=404, detail="Active assignment not found")
    from datetime import UTC, datetime

    assignment.revoked_at = datetime.now(UTC)
    write_audit(
        db,
        action="user.role_revoked",
        summary="Authorization role revoked",
        result="success",
        user_id=actor.id,
        entity_type="user",
        entity_id=user_id,
    )
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/admin/employees/{employee_id}/function-roles", status_code=status.HTTP_201_CREATED)
def assign_employee_function_role(
    employee_id: uuid.UUID,
    payload: FunctionRoleAssignmentCreate,
    actor: User = Depends(require_permission("employees.edit")),
    db: Session = Depends(get_db),
):
    employee = db.get(Employee, employee_id)
    function_role = db.get(EmployeeFunctionRole, payload.function_role_id)
    if employee is None or function_role is None:
        raise HTTPException(status_code=404, detail="Employee or function role not found")
    db.add(
        EmployeeFunctionRoleAssignment(
            employee_id=employee_id,
            function_role_id=payload.function_role_id,
        )
    )
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Function role already assigned") from exc
    write_audit(
        db,
        action="employee.function_role_assigned",
        summary="Employee business function assigned",
        result="success",
        user_id=actor.id,
        entity_type="employee",
        entity_id=employee_id,
        metadata={"function_role_id": str(payload.function_role_id)},
    )
    db.commit()
    return {"employee_id": employee_id, "function_role_id": payload.function_role_id}
