import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.modules.identity.models import EmploymentType, ScopeType


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=1, max_length=512)


class LoginResponse(BaseModel):
    must_change_password: bool


class CurrentUserResponse(BaseModel):
    id: uuid.UUID
    employee_id: uuid.UUID
    username: str
    is_superuser: bool
    must_change_password: bool
    permissions: list[str]


class EmployeeCreate(BaseModel):
    full_name: str = Field(min_length=1, max_length=255)
    position: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=64)
    email: str | None = Field(default=None, max_length=320)
    employment_type: EmploymentType = EmploymentType.STAFF


class EmployeeResponse(EmployeeCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    version: int


class UserCreate(BaseModel):
    employee_id: uuid.UUID
    username: str = Field(min_length=3, max_length=120)
    password: str = Field(min_length=12, max_length=512)
    is_active: bool = True
    is_superuser: bool = False
    must_change_password: bool = True


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    employee_id: uuid.UUID
    username: str
    is_active: bool
    is_superuser: bool
    must_change_password: bool


class RoleAssignmentCreate(BaseModel):
    role_id: uuid.UUID
    scope_type: ScopeType
    scope_config: dict[str, Any] | None = None


class AdminPasswordResetRequest(BaseModel):
    temporary_password: str = Field(min_length=12, max_length=512)
    reason: str | None = Field(default=None, max_length=1000)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=512)
    new_password: str = Field(min_length=12, max_length=512)


class RoleCreate(BaseModel):
    code: str = Field(pattern=r"^[a-z][a-z0-9_]{1,79}$")
    name: str = Field(min_length=1, max_length=160)
    is_system: bool = False


class PermissionGrant(BaseModel):
    permission_code: str = Field(pattern=r"^[a-z][a-z0-9_]*\.[a-z0-9_]+$", max_length=160)


class FunctionRoleAssignmentCreate(BaseModel):
    function_role_id: uuid.UUID
