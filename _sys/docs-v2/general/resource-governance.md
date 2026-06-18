# General — AI Resource Governance

> Status: DRAFT v2 (리서치 기반 전면 보완 2026-06-18 — cc+gc 끝장토론 + 3-agent web research)
> Renamed from: `token-management.md` (범위 확장)
> Scope: 모델 인벤토리 → 파라미터 참조 → 노드 아키텍처 → 역할 할당 → 라우팅 레이어 → 비용/품질 최적화 → 피드백 루프 → 지속 업데이트 방안

---

## 1. Per-Peer Model Inventory

### 1.1 cc — Claude (Anthropic)

#### 모델 전체 목록

| 모델 ID | Context | Max Output | 상태 | Thinking | 비고 |
|---------|--------:|----------:|------|----------|------|
| claude-haiku-4-5-20251001 | 200,000 | 4,096 | GA | ✗ | 빠른 분류·요약 (standard) |
| claude-sonnet-4-6 | 1,000,000 | 128,000 | GA | ✓ adaptive | 구현·협업 (effort) |
| claude-opus-4-7 | 200,000 | 128,000 | GA | ✓ adaptive | 고성능 추론 |
| claude-opus-4-8 | 1,000,000 | 128,000 | GA | ✓ adaptive | 최고 추론 (deepthink) |
| claude-fable-5 | 1,000,000 | 128,000 | GA* | ✓ adaptive | 저지연·플래그십 |
| claude-mythos-5 | 1,000,000 | 128,000 | 제한접근 | ✓ adaptive | 파트너 한정 |

> ⚠️ 기존 문서 오류: opus/sonnet max output `4,096` → `128,000`, opus/sonnet/fable context `200k` → `1M`

#### API 파라미터

| 파라미터 | 유효값 / 범위 | CLI | API | 지원 모델 | 비고 |
|---------|-------------|:---:|:---:|----------|------|
| `model` | 모델 ID | ✓ | ✓ | 전체 | |
| `max_tokens` | 1 ~ 모델 output 한도 | — | ✓ | 전체 | |
| `temperature` | 0.0 ~ 1.0 | — | ✓ | haiku/sonnet/fable only | **opus-4-7+ 미지원 (400 오류)** |
| `top_p` | 0.0 ~ 1.0 | — | ✓ | haiku/sonnet/fable only | opus-4-7+ 미지원 |
| `top_k` | 정수 | — | ✓ | haiku/sonnet/fable only | opus-4-7+ 미지원 |
| `thinking.type` | `"adaptive"` | — | ✓ | sonnet-4-6 / opus-4-7+ / fable-5 | 구 `budget_tokens` deprecated |
| `thinking.effort` | `low\|medium\|high\|max` | — | ✓ | thinking 지원 모델 | |
| `tool_choice` | `auto\|any\|none\|{type:"tool"}` | — | ✓ | 전체 | thinking 시 `auto`/`none`만 |
| `--betas` | beta header 문자열 | ✓ | — | API key only | `output-300k-2026-03-24` 등 |
| `--max-turns` | 정수 | ✓ | — | cc CLI | 자율 실행 제한 |

**Extended Thinking (Adaptive)**

| Effort | 정확도 | 출력 토큰 | 용도 |
|--------|--------|----------|------|
| low | ~55% | -40% | 빠른 초안, 분류 |
| medium | ~61% | -23% | 균형 (기본) |
| high | 최대 | 표준 | 복잡 추론·아키텍처 |
| max | 최대 | +α | 가장 어려운 문제 |

> ⚠️ Thinking 토큰은 output 토큰 요금으로 합산. `budget_tokens`는 deprecated.
> Beta header `output-300k-2026-03-24` 사용 시 최대 300k output 지원 (opus-4-6+, sonnet-4-6).

**Prompt Caching**

| 모델 | 지원 | 최소 토큰 | 캐시 히트 비용 | 쓰기 프리미엄 |
|------|------|----------|-------------|------------|
| haiku-4-5 | ✓ | 1,024 | 입력의 10% | +25% |
| sonnet-4-6 | ✓ | 1,024 | 입력의 10% | +25% |
| opus-4-7/4-8 | ✓ | 1,024 | 입력의 10% | +25% |
| fable-5 / mythos-5 | ✓ | 1,024 | 입력의 10% | +25% |

---

### 1.2 gc — Gemini (Google)

#### 모델 전체 목록

| 모델 ID | Context | Max Output | 상태 | Thinking | 비고 |
|---------|--------:|----------:|------|----------|------|
| gemini-3.5-flash | 1,000,000 | 65,536 | GA (2026-05) | thinking_level | EOL된 2.0-flash 대체 |
| gemini-3.1-pro | 1,000,000 | 미확인 | GA (2026-02) | thinking_level | 2M는 단일문서 처리 한도 |
| gemini-3-pro | 1,000,000 | 미확인 | GA | thinking_level | |
| gemini-3-flash | 1,000,000 | 미확인 | GA | thinking_level | |
| gemini-3.1-flash-lite | 미확인 | 미확인 | Preview | 미확인 | |
| gemini-2.5-pro | 1,000,000 | **24,576** | GA | thinking_budget (Always On) | |
| gemini-2.5-flash | 1,000,000 | 미확인 | GA | thinking_budget (끄기 가능) | |
| gemini-2.5-flash-lite | 미확인 | 미확인 | GA (Vertex) | 기본 OFF | |
| ~~gemini-2.0-flash~~ | — | — | **EOL 2026-06-01** | — | 사용 금지 |
| ~~gemini-2.0-flash-lite~~ | — | — | **EOL 2026-06-01** | — | |

> ⚠️ 기존 문서 오류: gemini-2.5-pro max output `65,536` → `24,576` / gemini-3.1-pro context `2M` → `1M`
> ⚠️ gemini-3-deep-think: 웹 리서치로 확인 불가 — 문서에서 제거

#### API 파라미터

| 파라미터 | 유효값 / 범위 | CLI | API | 지원 모델 | 비고 |
|---------|-------------|:---:|:---:|----------|------|
| `--model` / `-m` | 모델 ID | ✓ | ✓ | 전체 | |
| `--temperature` | 0.0 ~ **1.0** | ✓ | ✓ | 전체 | 추론 태스크 1.0 권장; 낮추면 루프 위험 |
| `--max_output_tokens` | 1 ~ 모델 상한 | ✓ | ✓ | 전체 | |
| `top_p` | 0.0 ~ 1.0 (기본 0.95) | — | ✓ | 전체 | |
| `top_k` | 1 ~ 40 (기본 40) | — | ✓ | 전체 | |
| `thinking_budget` | 0 ~ **24,576** (-1=dynamic) | — | ✓ | 2.5-pro/flash | 0=OFF (flash만), -1=자동 |
| `thinking_level` | `minimal\|low\|medium\|high` | ✓ | ✓ | 3.x 시리즈 | `thinking_budget`과 동시 사용 불가 |
| `--sandbox` | flag | ✓ | — | gc CLI | |
| `--yolo` | flag | ✓ | — | gc CLI | 승인 생략 |
| `--worktree` / `-w` | flag | ✓ | — | gc CLI | |

**Thinking 파라미터 상세**

| 모델 | 방식 | Thinking 끄기 | 청구 |
|------|------|------------|------|
| gemini-2.5-pro | `thinking_budget` | 불가 (Always On) | output 토큰으로 합산 |
| gemini-2.5-flash | `thinking_budget` | 가능 (0 설정) | output 토큰으로 합산 |
| gemini-2.5-flash-lite | — | 기본 OFF | — |
| gemini-3.x | `thinking_level` | `minimal` 사용 | output 토큰으로 합산 |

**Context Caching**

| 구분 | 최소 토큰 | 지원 모델 | 비용 절감 |
|------|----------|----------|---------|
| Implicit caching | 1,024 (flash) ~ 2,048 (pro) | 2.5+, 3.x | 입력의 90% 할인 (10% 지불) |
| Explicit caching | **32,768** | 2.5+, 3.x | 90% 할인 + 저장 $1/1M토큰/시간 |

---

### 1.3 cx — Codex (OpenAI)

#### 모델 전체 목록

| 모델 ID | Context | Max Output | 상태 | reasoning_effort | 비고 |
|---------|--------:|----------:|------|----------------|------|
| **gpt-5.5** | 1,000,000 | 128,000 | GA (2026-04) | none/low/medium/high/xhigh | 현재 config.toml 기본 모델 |
| gpt-5.5-pro | 1,000,000 | 128,000 | GA | none/low/medium/high/xhigh | ChatGPT Pro 전용 |
| gpt-5.4 | 1,000,000 | 128,000 | GA | 확인 중 | |
| gpt-5.4-mini | 400,000 | 128,000 | GA | 확인 중 | 빠른 서브에이전트용 |
| o3 | 200,000 | **100,000** | GA (단종 예정\*) | low/medium/high | \*ChatGPT 2026-08-26 단종, API 2026-10 |
| o3-pro | 200,000 | 100,000 | GA (2026-06-10) | 확인 중 | 전문가 수준 추론 |
| o3-mini | 200,000 | 100,000 | GA | low/medium/high | 경량 추론 |
| ~~o4-mini~~ | — | — | **단종** (ChatGPT 2026-02-13, API 2026-10) | — | peers.json 교체 필요 |
| ~~codex-mini-latest~~ | — | — | **Deprecated** | — | gpt-5.5로 대체됨 |

> ⚠️ 기존 문서 오류: o3 max output `65,536` → `100,000` / o4-mini는 단종 / codex-mini-latest deprecated

#### API 파라미터

| 파라미터 | 유효값 / 범위 | CLI (-c) | API | 지원 모델 | 비고 |
|---------|-------------|:--------:|:---:|----------|------|
| `model` | 모델 ID | ✓ | ✓ | 전체 | `-c model="gpt-5.5"` |
| `model_reasoning_effort` | `none\|low\|medium\|high\|xhigh` | ✓ | — | gpt-5.5 (5단계) | config.toml 기본 `medium` |
| `reasoning_effort` | `low\|medium\|high` | — | ✓ | o3/o3-mini | Chat Completions API |
| `reasoning.effort` | `low\|medium\|high\|xhigh` | — | ✓ | gpt-5.5 등 | Responses API (권장) |
| `-s` / `--sandbox` | `read-only\|workspace-write\|danger-full-access` | ✓ | — | cx CLI | ⚠️ v0.140.0부터 `full` 폐기 |
| `--json` | flag | ✓ | — | cx CLI | JSONL 이벤트 스트림 출력 |
| `-o` / `--output-last-message` | 파일 경로 | ✓ | — | cx CLI | 마지막 메시지를 파일로 저장 |
| `--ephemeral` | flag | ✓ | — | cx CLI | 세션 파일 미저장 |
| `model_verbosity` | `minimal\|normal\|verbose` | ✓ | — | cx CLI | |
| `web_search` | `cached\|live\|disabled` | ✓ | — | cx CLI | |

**reasoning_effort 레벨별 특성 (gpt-5.5 기준)**

| 레벨 | 내부 추론 | 속도 | 비용 | 적합 태스크 |
|------|---------|------|------|------------|
| none | 최소 | 최고속 | 최저 | 음성, 빠른 분류 |
| low | 경량 | 빠름 | 낮음 | 도구 호출, 검색, 계획 |
| medium | 균형 (기본값) | 중간 | 중간 | 일반 구현·협업 |
| high | 심층 | 느림 | 높음 | 복잡 디버깅·코드 리뷰 |
| xhigh | 최대 | 가장 느림 | 최고 | 최난도 알고리즘·보안 분석 |

> AIME 2024 기준: low→high 전환 시 정확도 10~30% 향상

**Reasoning 토큰 추적 (중요 수정)**

기존 문서의 "stdout 미노출" → **오류**. 실제로는 API usage 오브젝트에서 확인 가능:

```json
// Chat Completions API response
{
  "usage": {
    "output_tokens_details": {
      "reasoning_tokens": 4820   ← 실측 가능
    }
  }
}
```

→ Static Reserve 방식 보완 가능: 초기엔 예산 예약, 실측값 축적 후 동적 조정.

**Prompt Caching (gpt-5.5)**

- Extended prompt cache: 24시간 보관
- 캐시 히트 비용: $0.50/1M 토큰 (기본 $5/1M 대비 90% 할인)
- 추적: `usage.prompt_tokens_details.cached_tokens`

---

### 1.4 ag — Antigravity

| 상태 | INACTIVE |
|------|----------|
| health.json | 없음 |
| 모델 | default (미확인) |
| 파라미터 | 미확인 — 복구 후 별도 조사 필요 |

---

## 2. 즉시 수정 필요 항목

| 우선순위 | 항목 | 현재값 | 수정값 | 영향 |
|---------|------|--------|--------|------|
| 🔴 P0-A | gc standard 모델 | `gemini-2.0-flash` | `gemini-3.5-flash` | EOL 모델 호출 방지 |
| 🔴 P0-B | cx sandbox flag (hub.py) | `--sandbox full` | `--sandbox danger-full-access` | cx 호출 오류 수정 |
| 🔴 P0-C | peers.json cc context_limit | `200,000` (opus/sonnet) | `1,000,000` | ContextGate 오판 방지 |
| 🔴 P0-D | peers.json cc output_limit | `4,096` (opus/sonnet/fable) | `128,000` | Output Tier 오작동 방지 |
| 🟡 P1-A | cx peers.json 모델 교체 | `o4-mini` (effort) | `gpt-5.5` 또는 `o3` | 단종 모델 제거 |
| 🟡 P1-B | cx peers.json standard | `codex-mini-latest` | `gpt-5.5` | deprecated 제거 |
| 🟡 P1-C | cx reasoning_effort 레벨 | `low/medium/high` | gpt-5.5: `none~xhigh` 5단계 | 파라미터 정확성 |
| 🟡 P1-D | cc Extended Thinking API | `budget_tokens` | `thinking.type="adaptive" + effort` | deprecated API 교체 |
| 🟢 P2 | peers.json capacity 필드 전체 | string | 객체 (아래 스키마) | ContextGate 기반 |

---

## 3. ContextGate v1.0 설계 (cc+gc 합의, 수치 수정 반영)

### 3.1 peers.json 스키마 확장

`model_profiles` 값을 `string → object` 로 변경 (수정된 실측값 반영):

```json
// cc (Claude)
"model_profiles": {
  "standard":  { "model_id": "claude-haiku-4-5-20251001", "context_limit": 200000,   "output_limit": 4096,   "reasoning_budget": 0,     "thinking": false },
  "effort":    { "model_id": "claude-sonnet-4-6",         "context_limit": 1000000,  "output_limit": 128000, "reasoning_budget": 20000, "thinking": "adaptive" },
  "deepthink": { "model_id": "claude-opus-4-8",           "context_limit": 1000000,  "output_limit": 128000, "reasoning_budget": 50000, "thinking": "adaptive" }
}

// gc (Gemini)
"model_profiles": {
  "standard":  { "model_id": "gemini-3.5-flash", "context_limit": 1000000,  "output_limit": 65536, "reasoning_budget": 0,     "thinking": "thinking_level" },
  "effort":    { "model_id": "gemini-2.5-pro",   "context_limit": 1000000,  "output_limit": 24576, "reasoning_budget": 12000, "thinking": "always_on" },
  "deepthink": { "model_id": "gemini-2.5-pro",   "context_limit": 1000000,  "output_limit": 24576, "reasoning_budget": 24576, "thinking": "always_on" }
}

// cx (Codex/OpenAI)
"model_profiles": {
  "standard":  { "model_id": "gpt-5.5", "context_limit": 1000000, "output_limit": 128000, "reasoning_budget": 0,     "thinking": "reasoning_effort:low" },
  "effort":    { "model_id": "gpt-5.5", "context_limit": 1000000, "output_limit": 128000, "reasoning_budget": 30000, "thinking": "reasoning_effort:high" },
  "deepthink": { "model_id": "o3",      "context_limit": 200000,  "output_limit": 100000, "reasoning_budget": 60000, "thinking": "reasoning_effort:high" }
}
```

**하위호환:** `_resolve_model_profile(val)` — string이면 safe default 반환, dict이면 그대로 사용. 2커밋 후 string 지원 종료.

---

### 3.2 CJK 토큰 밀도 추정

```python
import re

def _estimate_tokens(text: str) -> int:
    """한국어/영문 혼합 텍스트 토큰 수 추정. +10% 버퍼 포함."""
    cjk_chars = len(re.findall(r'[가-힣一-鿿぀-ゟ]', text))
    total_chars = len(text)
    cjk_ratio = cjk_chars / total_chars if total_chars > 0 else 0

    if cjk_ratio < 0.01:     # ASCII 우세 (코드, 영문)
        rate = 0.25           # ~4 chars/token
    elif cjk_ratio < 0.30:   # 혼합 (코드 + 한국어 주석)
        rate = 1.2
    else:                     # 한국어 우세 (문서, 대화)
        rate = 1.8            # 실측 기준 (gc 원안 2.5에서 수정)

    return int(total_chars * rate * 1.1)  # +10% 안전 버퍼
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
  ├─ 5. if 초과 >= 10%
  │      → Transparent Failover to gc (1M context)
  │        - stdout: "[ContextGate] Rerouted to gc — Xk tokens exceeded {peer}:{tier} limit"
  │        - health.json session_usage.failover_count += 1
  │      (참고: cc sonnet/opus/fable는 1M context이므로 haiku standard에서만 주로 발동)
  │
  └─ 6. if tokens > 900k → sys.exit(2) 블로킹 (gc 한도 초과)
```

**Reasoning 토큰 추적 전략 (cx 개선)**

```python
# cx는 API usage에서 reasoning_tokens 실측 가능
# → session 누적 후 per-effort 평균 수렴 시 dynamic budget 전환 가능
# 초기: static reserve (peers.json reasoning_budget 사용)
# 10회 이상 실측 후: 평균값으로 budget 자동 조정
reasoning_tokens_observed = response["usage"]["output_tokens_details"]["reasoning_tokens"]
```

---

### 3.4 Output Tier 자동 승급

caller가 명시적으로 선언:

```python
expected_output_size: "short" | "medium" | "long" | "full_file"

OUTPUT_SIZE_TOKENS = {
    "short":      512,
    "medium":    2048,
    "long":      8192,
    "full_file":  None,  # profile output_limit 사용
}

# standard(haiku: 4096) 이면서 long/full_file 요청 → effort 자동 승급
if required_output > profile["output_limit"]:
    tier = "effort"
```

---

### 3.5 Reasoning Budget 처리

- `reasoning_budget`: `context_limit`에서 **선차감** 후 usable context 계산
- 값은 peers.json이 SSOT (hub.py 하드코딩 금지)
- cc: `thinking: "adaptive"` 방식 → effort 레벨이 budget을 결정 (숫자 지정 불가)
- cx: `reasoning_effort` 파라미터가 budget 결정. `reasoning_tokens` API로 실측 추적 가능
- gc: `thinking_budget` (2.5-pro: 0~24,576 / Always On), `thinking_level` (3.x)

---

## 4. 구현 우선순위

| 순서 | 작업 | 파일 | 비고 |
|------|------|------|------|
| P0-A | gc standard 모델 교체 | peers.json | gemini-3.5-flash |
| P0-B | cx sandbox flag 수정 | hub.py (cx 호출부) | `full` → `danger-full-access` |
| P0-C/D | cc context/output_limit 수정 | peers.json | 1M/128k 반영 |
| P1 | cx 모델 갱신 + reasoning_effort 레벨 | peers.json | o4-mini→deprecated, gpt-5.5 등록 |
| P2 | `_resolve_model_profile()` + 스키마 전환 | peers.json, hub.py | 하위호환 마이그레이션 |
| P3 | `_estimate_tokens()` CJK 추정 함수 | hub.py | 삼분법 적용 |
| P4 | ContextGate 흐름 | hub.py action_ask | Pruning + Failover + 로깅 |
| P5 | Output Tier 승급 | hub.py | expected_output_size 파라미터 |
| P6 | cx reasoning_tokens 실측 추적 | hub.py | dynamic budget 수렴 |

---

## 5. 미결 항목

- [ ] gemini-3.x 시리즈 max output 정확한 수치 확인 (현재 미확인)
- [ ] gpt-5.4 / gpt-5.4-mini reasoning_effort 지원 레벨 확인
- [ ] o3-pro reasoning_effort 지원 여부 확인
- [ ] cc claude-opus-4-7 peers.json 등록 여부 결정 (현재 미등록)
- [ ] cc claude-mythos-5 접근 가능 여부 확인 (제한 접근)
- [ ] ag (Antigravity) 복구 후 모델/파라미터 전체 조사
- [ ] cx 복구 후 gpt-5.5 실제 context_limit 실측 (API 기준 확인)
- [ ] Rate limit (RPM/TPM) 피어별 실측 — 현재 조직별 상이하여 문서화 보류

---

_cc+gc+3-agent research 합의 완료 2026-06-18. v1 대비 수정: cc context/output 전면, gc thinking_budget/temperature 수정, cx o4-mini 단종·gpt-5.5 추가, reasoning 토큰 실측 가능성 반영._
