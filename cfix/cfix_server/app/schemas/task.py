from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class TaskCaseIn(BaseModel):
    src_type: str = 'custom'
    case_in: str | None = None
    expect_out: str | None = None
    assert_text: str
    weight: float = 1.0
    sort_no: int = 1


class TaskCreate(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    sess_id: int | None = None
    model_id: int | None = None
    title: str
    lang: str = 'python'
    scene: str = 'func'
    dataset: str = 'custom'
    problem_text: str
    max_round: int = 3
    is_trace_on: bool = True
    is_lesson_on: bool = True
    cases: list[TaskCaseIn] = Field(default_factory=list)


class GenCaseCfg(BaseModel):
    count: int = Field(default=8, ge=4, le=30)
    preset: str = 'standard'
    focus: str = 'balanced'
    hint: str = ''


class GenTaskIn(BaseModel):
    auto_gen_cases: bool = False
    case_cfg: GenCaseCfg = Field(default_factory=GenCaseCfg)


class RunTaskIn(BaseModel):
    cases: list[TaskCaseIn] | None = None


class AutoFixIn(BaseModel):
    max_round: int = 3
    trace_on: bool | None = None
    lesson_on: bool | None = None
    stop_on_pass: bool | None = None
    cases: list[TaskCaseIn] | None = None


class TaskCaseReplaceIn(BaseModel):
    cases: list[TaskCaseIn] = Field(default_factory=list)


class CaseGenIn(BaseModel):
    problem_text: str
    scene: str = 'func'
    title: str = ''
    count: int = Field(default=8, ge=4, le=30)
    preset: str = 'standard'
    focus: str = 'balanced'
    hint: str = ''


class TaskUpdateIn(BaseModel):
    sess_id: int | None = None
    title: str | None = None
    lang: str | None = None
    scene: str | None = None
    dataset: str | None = None
    problem_text: str | None = None
    max_round: int | None = Field(default=None, ge=1, le=10)
    is_trace_on: bool | None = None
    is_lesson_on: bool | None = None
