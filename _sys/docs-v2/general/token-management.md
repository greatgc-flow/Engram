# General — Token & Context Management

> Status: DRAFT (cc+gc debate consensus 2026-06-18, pending implementation)
> Purpose: Per-peer model inventory, parameter reference, and ContextGate v1.0 design spec.

---

## 1. Per-Peer Model Inventory

### 1.1 cc — Claude (Anthropic)

| Tier | Model ID | Context | Max Output | 비고 |
|------|----------|--------:|----------:|------|
| standard | claude-haiku-4-5-20251001 | 200,000 | 4,096 | 빠른 분류·요약 |
| effort | claude-sonnet-4-6 | 200,000 | 4,096 | 구현·멀티파일·협업 |
| deepthink | claude-opus-4-8 | 200,000 | 4,096 | 아키텍처·복잡 추론, Extended Thinking |
| (미등록) | claude-fable-5 | 100,000 | 4,096 | 저지연 특화 |

**파라미터:**

| 파라미터 | 범위 / 값 | 접근 |
|---------|----------|------|
| `--model` | 모델 ID 문자열 | CLI |
| `--betas` | `interleaved-thinking-2025-05-14` 등 | CLI (API key only) |
| `--max-turns` | 정수 | CLI |
| thinking budget | 정수 (토큰 수) | API only (CLI 미지원) |

**주의:** Extended Thinking 토큰은 output 토큰으로 합산 청구. CLI에서 직접 제어 불가.

---

### 1.2 gc — Gemini (Google)

| Tier | Model ID | Context | Max Output | 상태 |
|------|----------|--------:|----------:|------|
| standard | ~~gemini-2.0-flash~~ | 1M | 8,192 | ⚠️ **EOL 2026-06-01** |
| standard (교체) | gemini-3.5-flash | 1M | 32,768 | 권장 교체 대상 |
| effort | gemini-2.5-pro | 1M | 65,536 | 현행 |
| deepthink | gemini-2.5-pro | 1M | 65,536 | Thinking Always On |
| (미등록) | gemini-3.1-pro | **2M** | 65,536 | 신규, 최대 컨텍스트 |
| (미등록) | gemini-3-deep-think | 512k | 131,072 | 특수 추론 전용 |

**파라미터:**

| 파라미터 | 범위 / 값 | 접근 | 비고 |
|---------|----------|------|------|
| `--model` | 모델 ID | CLI | |
| `--temperature` | 0.0 ~ 2.0 | CLI/API | 추론 태스크 1.0 권장 (0에 가까우면 루프 위험) |
| `--max_output_tokens` | 모델별 상한 | CLI | |
| `--thinking_level` | MINIMAL/LOW/MEDIUM/HIGH | CLI | 3.x 신규 |
| `thinking_budget` | 0 ~ 32,768 (-1=Auto) | API only | 2.5-pro 레거시 |
| `top_p` | 0.0 ~ 1.0 (기본 0.95) | API | |
| `top_k` | 1 ~ 40 (기본 40) | API | |

**Thinking 토큰 청구:** 내부 CoT 토큰은 **output 토큰 요금으로 합산**. 2.5-pro Thinking Always On.

---

### 1.3 cx — Codex (OpenAI)

| Tier | Model ID (peers.json) | 실제 config.toml | Context | Max Output |
|------|----------------------|-----------------|--------:|----------:|
| standard | codex-mini-latest | — | ~200k | 4,096 |
| effort | o4-mini | — | 200k | 65,536 |
| deepthink | o3 | — | 200k | 65,536 |
| (실제 사용중) | — | **gpt-5.5** | TBD | TBD |

> ⚠️ **peers.json과 config.toml 불일치**: cx 실제 동작 모델은 `gpt-5.5`
> (`~/.codex/config.toml` 기준), peers.json 등록값과 다름. 동기화 필요.

**파라미터:**

| 파라미터 | 범위 / 값 | 접근 | 비고 |
|---------|----------|------|------|
| `-m` / `--model` | 모델 ID | CLI | |
| `-s` / `--sandbox` | `read-only` \| `workspace-write` \| `danger-full-access` | CLI | ⚠️ v0.140.0부터 `full` → `danger-full-access` |
| `-c model_reasoning_effort` | `low` \| `medium` \| `high` | CLI (-c TOML) | **핵심 파라미터** |
| `-c model="o3"` | 모델 ID | CLI (-c TOML) | config override |
| `--ephemeral` | flag | CLI | 세션 파일 미저장 |
| `--json` | flag | CLI | JSONL 출력 (파싱 용이) |

**Reasoning 토큰:** `model_reasoning_effort` 로 예산 간접 제어. 실제 토큰 수는 stdout 미노출.

---

### 1.4 ag — Antigravity

| 상태 | INACTIVE |
|------|----------|
| health.json | 없음 |
| 모델 | default (미확인) |

---

## 2. 즉시 수정 필요 항목

| 우선순위 | 항목 | 현재값 | 수정값 | 영향 |
|---------|------|--------|--------|------|
| 🔴 P0 | gc standard 모델 | `gemini-2.0-flash` | `gemini-3.5-flash` | EOL 모델 호출 방지 |
| 🔴 P0 | hub.py cx sandbox flag | `--sandbox full` | `--sandbox danger-full-access` | cx 호출 오류 수정 |
| 🟡 P1 | cx peers.json 모델 동기화 | `codex-mini-latest` 등 | config.toml 실제값 반영 | 모델 불일치 해소 |
| 🟢 P2 | peers.json capacity 필드 | 모델명 string | 객체 (아래 스키마) | ContextGate 기반 |

---

## 3. ContextGate v1.0 설계 (cc+gc 합의)

### 3.1 peers.json 스키마 확장

`model_profiles` 값을 `string → object` 로 변경:

```json
// 예: cc (Claude) peers.json 확장
"model_profiles": {
  "standard": {
    "model_id": "claude-haiku-4-5-20251001",
    "context_limit": 200000,
    "output_limit": 4096,
    "reasoning_budget": 0
  },
  "effort": {
    "model_id": "claude-sonnet-4-6",
    "context_limit": 200000,
    "output_limit": 4096,
    "reasoning_budget": 0
  },
  "deepthink": {
    "model_id": "claude-opus-4-8",
    "context_limit": 200000,
    "output_limit": 4096,
    "reasoning_budget": 32000
  }
}

// gc (Gemini)
"model_profiles": {
  "standard":  { "model_id": "gemini-3.5-flash", "context_limit": 1000000, "output_limit": 32768, "reasoning_budget": 0      },
  "effort":    { "model_id": "gemini-2.5-pro",   "context_limit": 1000000, "output_limit": 65536, "reasoning_budget": 20000  },
  "deepthink": { "model_id": "gemini-2.5-pro",   "context_limit": 1000000, "output_limit": 65536, "reasoning_budget": 32768  }
}

// cx (Codex) — config.toml 동기화 후 업데이트 필요
"model_profiles": {
  "standard":  { "model_id": "gpt-5.5",  "context_limit": 200000, "output_limit": 4096,  "reasoning_budget": 0     },
  "effort":    { "model_id": "o4-mini",  "context_limit": 200000, "output_limit": 65536, "reasoning_budget": 32000 },
  "deepthink": { "model_id": "o3",       "context_limit": 200000, "output_limit": 65536, "reasoning_budget": 64000 }
}
```

**하위호환:** `_resolve_model_profile(val)` — string이면 safe default 반환, dict이면 그대로 사용. 2커밋 후 string 지원 종료.

---

### 3.2 CJK 토큰 밀도 추정

```python
import re

def _estimate_tokens(text: str) -> int:
    """한국어/영문 혼합 텍스트 토큰 수 추정. +10% 버퍼 포함."""
    cjk_chars = len(re.findall(r'[가-힯一-鿿぀-ゟ]', text))
    total_chars = len(text)
    cjk_ratio = cjk_chars / total_chars if total_chars > 0 else 0

    if cjk_ratio < 0.01:        # ASCII 우세
        rate = 0.25
    elif cjk_ratio < 0.30:      # 혼합 (코드+한국어 주석)
        rate = 1.2
    else:                        # 한국어 우세
        rate = 1.8              # gc 원안 2.5 → 실측 기준 1.8로 수정

    return int(total_chars * rate * 1.1)
```

---

### 3.3 ContextGate 흐름 (hub.py action_ask)

```
action_ask(query, context, peer, tier, expected_output_size="medium")
  │
  ├─ 1. estimated_tokens = _estimate_tokens(query + context)
  │
  ├─ 2. profile = peers[peer]["model_profiles"][tier]
  │      usable = profile.context_limit - profile.reasoning_budget
  │
  ├─ 3. if estimated_tokens <= usable → 정상 진행
  │
  ├─ 4. if 초과 < 10% → Pruning 시도
  │      (handoff 저우선순위 섹션 제거 후 재추정)
  │      성공 → 정상 진행
  │
  ├─ 5. if 초과 >= 10% AND peer in (cc, cx) AND tokens <= 900k
  │      → Transparent Failover to gc
  │        - stdout: "[ContextGate] Rerouted to gc — Xk tokens exceeded {peer} limit"
  │        - health.json session_usage.failover_count += 1
  │
  └─ 6. if 초과 AND tokens > 900k → sys.exit(2) 블로킹
```

---

### 3.4 Output Tier 자동 승급

keyword 기반 휴리스틱 **제외** (fragile). 대신 명시적 파라미터:

```python
# hub.py ask 호출 시 caller가 선언
expected_output_size: "short" | "medium" | "long" | "full_file"

# 매핑
OUTPUT_SIZE_TOKENS = {
    "short":     512,
    "medium":   2048,
    "long":     8192,
    "full_file": None,  # 모델 profile output_limit 사용
}

# standard 티어 output_limit=4096인데 long/full_file 요청 시 → effort 자동 승급
if required_output > profile["output_limit"]:
    tier = "effort"
```

---

### 3.5 Reasoning Budget 처리

- `reasoning_budget` 을 `context_limit` 에서 **선차감** 후 usable context 계산
- 값은 peers.json이 SSOT (hub.py에 하드코딩 금지)
- `reasoning_budget: 0` = reasoning 없음 (haiku, flash 등)

---

## 4. 구현 우선순위

| 순서 | 작업 | 파일 | 비고 |
|------|------|------|------|
| P0-A | gc standard 모델 교체 | peers.json | gemini-3.5-flash |
| P0-B | cx sandbox flag 수정 | hub.py (cx 호출부) | `full` → `danger-full-access` |
| P1 | `_resolve_model_profile()` + peers.json capacity 확장 | peers.json, hub.py | 하위호환 마이그레이션 |
| P2 | `_estimate_tokens()` CJK 추정 함수 | hub.py | 삼분법 적용 |
| P3 | ContextGate 흐름 | hub.py action_ask | Pruning + Failover + 로깅 |
| P4 | Output Tier 승급 | hub.py | expected_output_size 파라미터 |
| P5 | Reasoning Budget 차감 | hub.py | deepthink 안정화 |

---

## 5. 미결 항목 (cx 복구 후 확인)

- [ ] cx 실제 사용 모델 (`gpt-5.5`) context_window / max_output 실측값
- [ ] cx `model_reasoning_effort` 실제 토큰 소비 패턴 확인
- [ ] gemini-3.1-pro (2M context) 정식 CLI 접근 가능 여부
- [ ] ag (Antigravity) 모델/파라미터 조사 (INACTIVE 해제 시)

---

_cc+gc 합의 완료 2026-06-18. cx는 sandbox 수정 및 복구 후 재참여 예정._
