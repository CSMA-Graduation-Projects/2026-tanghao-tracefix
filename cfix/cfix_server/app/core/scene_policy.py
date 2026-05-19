"""场景策略模块，负责提供后端运行所需的基础能力。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ScenePolicy:
    scene: str
    label: str
    case_mode: str
    accumulate_block_setup: bool
    prompt_focus: str
    trace_focus: str


_SCENE_MAP: dict[str, ScenePolicy] = {
    "func": ScenePolicy(
        scene="func",
        label="函数级",
        case_mode="line",
        accumulate_block_setup=False,
        prompt_focus=(
            "聚焦函数签名、返回值、边界条件和单函数逻辑正确性。"
        ),
        trace_focus=(
            "优先记录输入参数、关键中间变量和返回值。"
        ),
    ),
    "class": ScenePolicy(
        scene="class",
        label="类文件级",
        case_mode="block",
        accumulate_block_setup=False,
        prompt_focus=(
            "聚焦类名、构造函数、对象状态、公开方法协作和方法间数据流，不要退化成 solve 函数。"
        ),
        trace_focus=(
            "优先记录构造后的对象状态、方法调用顺序、属性变化和返回值。"
        ),
    ),
    "file": ScenePolicy(
        scene="file",
        label="完整模块级",
        case_mode="block",
        accumulate_block_setup=True,
        prompt_focus=(
            "聚焦完整模块 API、跨函数/跨类协作、模块级状态和公开接口兼容性，不要退化成 solve 函数。"
        ),
        trace_focus=(
            "优先记录模块公开 API 的协作路径、关键变量、分支走向和跨调用状态传递。"
        ),
    ),
}


def get_scene_policy(scene: str | None) -> ScenePolicy:
    key = str(scene or "func").strip().lower()
    return _SCENE_MAP.get(key, _SCENE_MAP["func"])
