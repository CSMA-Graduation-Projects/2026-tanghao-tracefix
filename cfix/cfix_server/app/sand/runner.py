from app.core.cfg import settings
from app.sand.docker_runner import DockerRunner
from app.sand.safe_exec import exec_python, exec_python_case


class Runner:
    """统一执行入口。

    按配置在两类后端间切换：
    1. safe_exec：宿主机最小原型，适合本地快速联调；
    2. docker：真实容器隔离执行，优先用于最终演示与实验。
    """

    def __init__(self):
        self._docker = DockerRunner() if settings.sandbox_use_docker else None

    def run(self, code_text: str, asserts: list[str]):
        return self.run_all(code_text, asserts)

    def run_all(self, code_text: str, asserts: list[str]):
        if self._docker:
            return self._docker.run(code_text, asserts)
        return exec_python(code_text, asserts)

    def run_one(self, code_text: str, assert_text: str):
        if self._docker:
            return self._docker.run_one(code_text, assert_text)
        return exec_python_case(code_text, assert_text)

    def run_trace_all(self, inst_code_text: str, asserts: list[str]):
        return self.run_all(inst_code_text, asserts)

    def run_trace_one(self, inst_code_text: str, assert_text: str):
        return self.run_one(inst_code_text, assert_text)
