FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# 方案 A: 直接使用已有的 nobody 用户 (UID 通常为 65534)
# 注意：不同发行版 nobody 的 GID 可能不同，这里假设 GID 为 0 (root) 或创建组
# 更稳妥的方式是创建一个新用户，但不硬编码 UID，或者检查 UID 是否可用

# 方案 B (推荐): 创建用户但不强制指定 UID 65534，或者使用已存在的 nobody
# 这里我们改用 nobody 用户，因为它通常就是用于无特权运行的
RUN mkdir -p /opt/cfix && chown -R nobody:nogroup /opt/cfix

COPY sandbox/py/runner.py /opt/cfix/runner.py

WORKDIR /opt/cfix
# 切换到 nobody 用户
USER nobody

CMD ["python", "-I", "-B", "/opt/cfix/runner.py"]