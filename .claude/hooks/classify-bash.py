#!/usr/bin/env python3
"""3-Tier Bash Classifier Hook (PreToolUse)

stdin으로 tool_input JSON을 받아 DENY/SAFE/ASK를 판정한다.
exit 2 = DENY (차단), exit 0 = SAFE (허용), exit 1 = 비차단 경고 (stderr 표시 후 Claude가 판단)
  ※ 진정한 ask 권한 UI는 JSON Decision Control(permissionDecision: "ask")로 구현 가능

Setup:
  chmod +x .claude/hooks/classify-bash.py
  # settings.json PreToolUse hooks에 등록 후 사용
"""
import json
import sys
import re

# --- DENY 패턴: 즉시 차단 (정규식) ---
# 프로젝트별 위험 명령을 여기에 추가
DENY_PATTERNS = [
    # <prohibited_actions>(절대금지) 미커버 항목만 포함
    # rm -rf는 <prohibited_actions>로 커버 → 불필요
    # git push --force / git reset --hard는 <explicit_permission>(ask 수준)
    # → settings.json deny로 강화됨. 여기에도 추가하면 hook 레벨 이중 보호 가능
    r"sudo\s+",                  # 모든 sudo
    r"chmod\s+777",              # 위험 권한
    r"eval\s+",                  # eval 실행
    r"curl\s+.*\|\s*bash",       # pipe to bash
    r"curl\s+.*\|\s*sh",         # pipe to sh
    r">\s*/etc/",                # 시스템 파일 덮어쓰기
    r"mkfs\.",                   # 디스크 포맷
    r"dd\s+if=",                 # 디스크 직접 쓰기
    # --- 프로젝트별 DENY 패턴 추가 ---
    # r"your-dangerous-command",
]

# --- SAFE 패턴: 자동 허용 (정규식) ---
# 프로젝트별 안전 명령을 여기에 추가
SAFE_PATTERNS = [
    r"^(npm|npx|yarn|pnpm)\s+(run\s+)?(test|lint|build|format|check)",
    r"^(pytest|ruff|mypy|cargo\s+(test|clippy|fmt)|go\s+(test|vet))",
    r"^git\s+(status|log|diff|branch|show|tag|stash\s+list)",
    r"^(ls|pwd|echo|wc|date|which|whoami)",
    # cat/head/tail은 SAFE에서 제외 — Bash로 민감 파일 읽기(cat .env) 시 Read deny 우회 방지
    r"^[a-zA-Z_-]+\s+--version$",
    r"^[a-zA-Z_-]+\s+--help$",
    # --- 프로젝트별 SAFE 패턴 추가 ---
    # r"^your-safe-command",
]


def classify(command: str) -> int:
    cmd = command.strip()
    for pattern in DENY_PATTERNS:
        if re.search(pattern, cmd):
            print(f"DENY: matched pattern '{pattern}'", file=sys.stderr)
            return 2  # DENY → 차단
    for pattern in SAFE_PATTERNS:
        if re.search(pattern, cmd):
            return 0  # SAFE → 허용
    return 1  # 비차단 경고: stderr 메시지를 표시하되 차단하지 않음 (Claude가 맥락에 따라 판단)


if __name__ == "__main__":
    try:
        data = json.load(sys.stdin)
        command = data.get("tool_input", {}).get("command", "")
        sys.exit(classify(command))
    except Exception:
        sys.exit(1)  # 파싱 실패 시 비차단 경고 (안전 기본값)
