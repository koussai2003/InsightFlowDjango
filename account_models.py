import os
from enum import StrEnum
import psycopg
from psycopg.rows import dict_row
from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

class Role(StrEnum):
    scientist = "data_scientist"
    reviewer = "reviewer"
    admin = "administrator"

class Credentials(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)

class Registration(Credentials):
    password: str = Field(min_length=12, max_length=128)

class Signup(Registration):
    confirm_password: str

    @model_validator(mode="after")
    def matching(self):
        if self.password != self.confirm_password:
            raise ValueError("Passwords must match")
        return self

class SecurityChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_password: str = Field(max_length=128)
    delete_account: bool = False
    new_email: EmailStr | None = None
    new_password: str | None = Field(default=None, min_length=12, max_length=128)
    confirm_password: str | None = None

    @model_validator(mode="after")
    def valid(self):
        if sum((self.delete_account, self.new_email is not None, self.new_password is not None)) != 1:
            raise ValueError("Choose one change at a time")
        if self.new_password is not None and self.new_password != self.confirm_password:
            raise ValueError("Passwords must match")
        return self

class RoleChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Role

def connect():
    return psycopg.connect(os.environ["DATABASE_URL"], row_factory=dict_row, connect_timeout=5)

def database():
    with connect() as connection:
        yield connection
