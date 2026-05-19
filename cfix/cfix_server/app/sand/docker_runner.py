"""Docker 沙箱执行器模块，负责代码执行隔离、调度与轨迹包装。"""

import json
import shutil
import subprocess
import uuid
from pathlib import Path, PurePosixPath
from typing import Iterable

from app.core.cfg import settings
from app.sand.safe_exec import ExecResult, _extract_line_no


_RESULT_PREFIX = "__CFIX_RESULT__"


class DockerRunner:
    """基于 docker CLI 的真实容器执行器。

    设计目标：
    1. 保持与 safe_exec 相同的返回结构，业务层无需大改。
    2. 通过 Docker 容器完成真正的隔离执行，而不是宿主进程内 exec。
    3. 提供最小可落地的资源限制、超时回收与临时目录清理。
    """

    def __init__(self):
        self.docker_bin = settings.sandbox_docker_bin
        self.image = settings.sandbox_image
        self.timeout_sec = settings.sandbox_timeout_sec
        self.work_root = Path(settings.sandbox_work_root)
        self.memory = settings.sandbox_memory
        self.cpus = settings.sandbox_cpus
        self.pids_limit = settings.sandbox_pids_limit
        self.read_only = settings.sandbox_read_only
        self.keep_temp = settings.sandbox_keep_temp

    def run(self, code_text: str, asserts: list[str]):
        return self._exec(code_text=code_text, asserts=asserts)

    def run_one(self, code_text: str, assert_text: str):
        return self._exec(code_text=code_text, asserts=[assert_text])

    def _exec(self, code_text: str, asserts: Iterable[str]):
        if not shutil.which(self.docker_bin):
            return ExecResult(
                ok=False,
                result="fail",
                stdout="",
                stderr="",
                tb_text="",
                err_type="SandboxUnavailableError",
                err_msg=f"未找到 docker 可执行文件：{self.docker_bin}",
                line_no=None,
                time_ms=0,
            )

        run_id = uuid.uuid4().hex[:12]
        container_name = f"cfix-sandbox-{run_id}"
        workdir = self.work_root / run_id
        workdir.mkdir(parents=True, exist_ok=True)
        code_file = workdir / "code.py"
        asserts_file = workdir / "asserts.txt"
        code_file.write_text(code_text or "", encoding="utf-8")
        asserts_file.write_text("\n".join(x for x in asserts if x), encoding="utf-8")

        cmd = self._build_docker_cmd(
            container_name=container_name,
            workdir=workdir,
            code_file=code_file,
            asserts_file=asserts_file,
        )

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout_sec + 3,
                encoding="utf-8",
                errors="replace",
            )
        except subprocess.TimeoutExpired:
            self._force_remove_container(container_name)
            result = ExecResult(
                ok=False,
                result="fail",
                stdout="",
                stderr="",
                tb_text="",
                err_type="TimeoutError",
                err_msg=f"Docker 沙箱执行超时（>{self.timeout_sec}s）",
                line_no=None,
                time_ms=self.timeout_sec * 1000,
            )
            self._cleanup(workdir)
            return result
        except Exception as exc:  # noqa: BLE001
            self._force_remove_container(container_name)
            result = ExecResult(
                ok=False,
                result="fail",
                stdout="",
                stderr="",
                tb_text="",
                err_type=exc.__class__.__name__,
                err_msg=f"Docker 沙箱执行失败：{exc}",
                line_no=None,
                time_ms=0,
            )
            self._cleanup(workdir)
            return result

        parsed = self._parse_result(proc.stdout, proc.stderr)
        if parsed is None:
            stderr = (proc.stderr or "").strip()
            stdout = (proc.stdout or "").strip()
            msg = stderr or stdout or "Docker 返回中未找到结构化执行结果"
            result = ExecResult(
                ok=False,
                result="fail",
                stdout=stdout,
                stderr=stderr,
                tb_text=stderr,
                err_type="SandboxProtocolError",
                err_msg=msg,
                line_no=_extract_line_no(stderr),
                time_ms=0,
            )
        else:
            result = parsed

        self._cleanup(workdir)
        return result

    def _build_docker_cmd(self, container_name: str, workdir: Path, code_file: Path, asserts_file: Path) -> list[str]:
        mount_mode = "ro" if self.read_only else "rw"
        cmd = [
            self.docker_bin,
            "run",
            "--rm",
            "--name",
            container_name,
            "--network",
            "none",
            "--security-opt",
            "no-new-privileges",
            "--cap-drop",
            "ALL",
            "--pids-limit",
            str(self.pids_limit),
            "--memory",
            str(self.memory),
            "--cpus",
            str(self.cpus),
            "--user",
            "65534:65534",
            "-e",
            "PYTHONDONTWRITEBYTECODE=1",
            "-e",
            "PYTHONUNBUFFERED=1",
            "-e",
            f"CFIX_TIMEOUT_SEC={self.timeout_sec}",
            "-v",
            f"{workdir.resolve()}:/work:{mount_mode}",
            "--tmpfs",
            "/tmp:rw,nosuid,nodev,noexec,size=64m",
        ]
        if self.read_only:
            cmd.extend(["--read-only"])

        # 重要：这里传给容器内 runner.py 的路径必须始终使用 POSIX 风格。
        #
        # 当前后端运行在 Windows 宿主机时，pathlib.Path("/work") 会变成 WindowsPath，
        # str(Path("/work") / "code.py") 可能得到 "\\work\\code.py"。
        # 这样的参数进入 Linux 容器后会被当成普通文件名而不是合法路径，
        # 从而触发 FileNotFoundError。
        #
        # 因此这里统一使用 PurePosixPath 构造容器内路径，确保永远是 /work/code.py。
        guest_code = str(PurePosixPath("/work") / code_file.name)
        guest_asserts = str(PurePosixPath("/work") / asserts_file.name)

        cmd.extend(
            [
                self.image,
                "python",
                "-I",
                "-B",
                "/opt/cfix/runner.py",
                guest_code,
                guest_asserts,
            ]
        )
        return cmd

    @staticmethod
    def _parse_result(stdout: str, stderr: str) -> ExecResult | None:
        lines = (stdout or "").splitlines()
        payload = None
        for line in reversed(lines):
            if line.startswith(_RESULT_PREFIX):
                payload = line[len(_RESULT_PREFIX) :]
                break
        if not payload:
            return None

        try:
            data = json.loads(payload)
        except Exception:  # noqa: BLE001
            return None

        tb_text = data.get("tb_text") or ""
        return ExecResult(
            ok=bool(data.get("ok")),
            result=data.get("result") or ("pass" if data.get("ok") else "fail"),
            stdout=data.get("stdout") or "",
            stderr=data.get("stderr") or stderr or "",
            tb_text=tb_text,
            err_type=data.get("err_type"),
            err_msg=data.get("err_msg"),
            line_no=data.get("line_no") or _extract_line_no(tb_text),
            time_ms=max(0, int(data.get("time_ms") or 0)),
        )

    def _force_remove_container(self, container_name: str) -> None:
        try:
            subprocess.run(
                [self.docker_bin, "rm", "-f", container_name],
                capture_output=True,
                text=True,
                timeout=5,
            )
        except Exception:  # noqa: BLE001
            pass

    def _cleanup(self, workdir: Path) -> None:
        if self.keep_temp:
            return
        shutil.rmtree(workdir, ignore_errors=True)
