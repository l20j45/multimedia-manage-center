"""Esquemas Pydantic (entrada/salida de la API)."""

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserBase(BaseModel):
    email: EmailStr
    name: str | None = None


class UserCreate(UserBase):
    password: str = Field(min_length=8, description="Mínimo 8 caracteres")


class UserUpdate(BaseModel):
    name: str | None = None
    current_password: str | None = None
    new_password: str | None = Field(None, min_length=8)


class UserOut(UserBase):
    id: int
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class Message(BaseModel):
    msg: str


class ForgotPasswordIn(BaseModel):
    email: EmailStr


class ResetPasswordIn(BaseModel):
    email: EmailStr
    code: str = Field(
        min_length=6, max_length=6, description="Código de 6 dígitos enviado por correo"
    )
    new_password: str = Field(min_length=8)
