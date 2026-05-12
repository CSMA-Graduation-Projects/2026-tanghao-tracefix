from __future__ import annotations

from pydantic import BaseModel, Field


class DatasetCaseIn(BaseModel):
    src_type: str = 'dataset'
    case_in: str | None = None
    expect_out: str | None = None
    assert_text: str
    weight: float = 1.0
    sort_no: int = 1


class DatasetItemIn(BaseModel):
    title: str
    scene: str = 'func'
    problem_text: str
    cases: list[DatasetCaseIn] = Field(default_factory=list)


class DatasetCreateIn(BaseModel):
    name: str
    display_name: str
    desc: str = ''
    initial_item: DatasetItemIn | None = None
