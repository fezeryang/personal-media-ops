from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.library import LibraryContentSummary


class NameWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)

    @field_validator("name")
    @classmethod
    def normalized(cls, value: str) -> str:
        result = value.strip()
        if not result or not result.isprintable():
            raise ValueError("name must be printable and non-blank")
        return result


class FavoriteWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_favorite: bool


class Tag(BaseModel):
    id: str
    name: str
    content_count: int
    created_at: str
    updated_at: str


class CollectionWrite(NameWrite):
    description: str | None = Field(default=None, max_length=1000)

    @field_validator("description")
    @classmethod
    def normalized_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        result = value.strip()
        return result or None


class CollectionItemWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content_id: str = Field(min_length=1, max_length=100)
    position: int = Field(ge=0)


class CollectionItem(BaseModel):
    content: LibraryContentSummary
    position: int
    created_at: str


class Collection(BaseModel):
    id: str
    name: str
    description: str | None
    content_count: int
    created_at: str
    updated_at: str


class CollectionDetail(Collection):
    items: list[CollectionItem]
