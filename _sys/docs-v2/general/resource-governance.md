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

---

## 6. 노드 아키텍처

### 6.1 노드 정의

**Node = (peer_id, model_id, thinking_config, sandbox_level)**

4차원 조합이 하나의 실행 단위. 동일 peer라도 설정이 다르면 다른 노드.

```
cc::haiku-4-5::none::none
cc::sonnet-4-6::adaptive:medium::none
cc::opus-4-8::adaptive:max::none
gc::gemini-3.5-flash::level:minimal::none
gc::gemini-2.5-pro::budget:12000::none
gc::gemini-2.5-pro::budget:24576::none
cx::gpt-5.5::effort:low::read-only
cx::gpt-5.5::effort:high::workspace-write
cx::o3::effort:high::danger-full-access
```

### 6.2 노드 특성 매트릭스

| 노드 ID | Context | Output | Input $/1M | Output $/1M | 속도 | 한국어 | 파일 쓰기 | 웹 검색 | 코드 실행 |
|---------|--------:|-------:|----------:|----------:|------|--------|----------|--------|---------|
| cc::haiku::none | 200k | 4k | $0.80 | $4.00 | ⚡⚡⚡ | ✓ | ✗ | ✗ | ✗ |
| cc::sonnet::adaptive:medium | 1M | 128k | $3.00 | $15.00 | ⚡⚡ | ✓✓ | ✓ | ✗ | ✗ |
| cc::opus::adaptive:max | 1M | 128k | $15.00 | $75.00 | ⚡ | ✓✓ | ✓ | ✗ | ✗ |
| gc::3.5-flash::minimal | 1M | 65k | $0.07 | $0.30 | ⚡⚡⚡ | ✓ | ✗ | ✓ | ✓ |
| gc::2.5-pro::budget:12000 | 1M | ~12k | $7.00 | $21.00 | ⚡⚡ | ✓ | ✗ | ✓ | ✓ |
| gc::2.5-pro::budget:24576 | 1M | ~4k | $7.00 | $21.00 | ⚡ | ✓ | ✗ | ✓ | ✓ |
| cx::gpt-5.5::effort:low::rw | 1M | 128k | $5.00 | $15.00 | ⚡⚡ | ✓ | ✓ | ✓ | ✓ |
| cx::gpt-5.5::effort:high::rw | 1M | 128k | $5.00 | $30.00 | ⚡ | ✓ | ✓ | ✓ | ✓ |
| cx::o3::effort:high::dfa | 200k | 100k | $2.00 | $8.00+ | ⚡ | ✓ | ✓ | ✗ | ✓ |

> **gc 2.5-pro 주의:** thinking_budget + output_tokens 공유 풀 = 24,576.
> budget=12,000 설정 시 실제 output 최대 ≈ 12,576토큰. budget=24,576 시 output ≈ 0.
> 실용 분할: `thinking_budget = min(complexity × 8000, 20000)`, reserved_output ≥ 4,576

### 6.3 노드별 품질 차원 (상대 점수 1~5)

| 노드 | 코드 생성 | 복잡 추론 | 문서 작성 | 한국어 품질 | 대용량 분석 | 보안 리뷰 |
|------|:--------:|:--------:|:--------:|:---------:|:---------:|:--------:|
| cc::haiku | 3 | 2 | 3 | 4 | 2 | 2 |
| cc::sonnet::medium | 5 | 4 | 5 | 5 | 4 | 4 |
| cc::opus::max | 5 | 5 | 5 | 5 | 4 | 5 |
| gc::3.5-flash | 3 | 3 | 4 | 3 | 5 | 3 |
| gc::2.5-pro::12k | 4 | 5 | 5 | 3 | 5 | 5 |
| cx::gpt-5.5::high | 5 | 5 | 4 | 3 | 4 | 5 |
| cx::o3::high | 5 | 5 | 3 | 3 | 3 | 5 |

---

## 7. 역할 분류 및 노드 매핑

### 7.1 역할 전체 분류 (MECE)

| # | 역할 | 설명 | 트리거 |
|---|------|------|--------|
| R01 | **Router/Triage** | 태스크 분석, 피어 선택, 미션 분해 | 모든 ask 진입 시 |
| R02 | **Implementer** | 코드 작성, 파일 생성, 리팩터 | write/edit 요청 |
| R03 | **Architect** | 시스템 설계, 의존성 분석, 프로토콜 결정 | 구조 변경 전 |
| R04 | **Code Reviewer** | 코드 리뷰, 보안 분석, 테스트 검증 | PR/완료 후 |
| R05 | **Doc Writer (KO)** | 한국어 문서 초안, 규격서, 요약 | docs 요청 |
| R06 | **Large Corpus Analyst** | 전체 repo 분석, 의존성 맵, 포화 감지 | saturation_scan |
| R07 | **Test Author** | TDD 테스트 작성, RED→GREEN 검증 | 구현 전/후 |
| R08 | **Debugger** | 버그 추적, 로그 분석, root cause | 실패 발생 시 |
| R09 | **Consensus Facilitator** | R:8+ 합의 진행, 투표 집계, ACK 확인 | 거버넌스 결정 |
| R10 | **Self-Care Executor** | self_care.py 단계 실행, 포화 제안 | session_end |
| R11 | **Escalation Handler** | 연속 실패, 교착 상태, 긴급 복구 | error_threshold>5 |
| R12 | **Fast QA** | 단순 검증, 형식 확인, lint 수준 | 빠른 체크 |

### 7.2 역할 → 노드 매핑

| 역할 | Primary 노드 | Fallback 노드 | 선택 이유 |
|------|-------------|-------------|---------|
| R01 Router | gc::3.5-flash::minimal | cc::haiku::none | 최저 비용, 빠른 분류 |
| R02 Implementer | cc::sonnet::adaptive:medium | cx::gpt-5.5::effort:medium | 한국어 코드, Tool use |
| R03 Architect | gc::2.5-pro::budget:12000 | cc::opus::adaptive:high | 대용량 컨텍스트, 깊은 추론 |
| R04 Code Reviewer | cx::gpt-5.5::effort:high | cc::sonnet::adaptive:high | 코드 전문성, reasoning 강점 |
| R05 Doc Writer (KO) | cc::sonnet::adaptive:low | cc::opus::adaptive:medium | 한국어 품질 최우선 |
| R06 Large Corpus | gc::2.5-pro::budget:0 | gc::3.5-flash::minimal | 1M context, 대용량 처리 |
| R07 Test Author | cc::sonnet::adaptive:medium | cx::gpt-5.5::effort:medium | TDD 패턴, Tool use |
| R08 Debugger | cx::gpt-5.5::effort:high | cc::opus::adaptive:high | reasoning 추론 강점 |
| R09 Consensus | cc::sonnet::adaptive:low | gc::3.5-flash::minimal | 프로토콜 이해, 낮은 비용 |
| R10 Self-Care | cc::haiku::none | gc::3.5-flash::minimal | 경량, 비차단 |
| R11 Escalation | cc::opus::adaptive:max | gc::2.5-pro::budget:20000 | 최고 추론, 최후 수단 |
| R12 Fast QA | cc::haiku::none | gc::3.5-flash::minimal | 최저 비용, 즉시 응답 |

### 7.3 노드 재사용 (동일 노드 N역할)

```
cc::sonnet::adaptive:medium  →  R02(Implementer) + R07(Test Author) + R09(Consensus)
gc::3.5-flash::minimal       →  R01(Router) + R10(Self-Care) + R12(Fast QA)
gc::2.5-pro::budget:12000    →  R03(Architect) + R06(Large Corpus)
cx::gpt-5.5::effort:high     →  R04(Code Reviewer) + R08(Debugger)
cc::opus::adaptive:max        →  R11(Escalation) — 전용 (비용 최고)
```

---

## 8. 5-레이어 라우팅 아키텍처

```
┌─────────────────────────────────────────────────────────────────┐
│  LAYER 0: Registry (모델 스펙 SSOT)                              │
│                                                                 │
│  model-registry.json  ← 모든 모델의 실측 스펙 (R:8 변경)         │
│       ↓ (파생)                                                   │
│  peers.json           ← 운영 매핑만 (standard/effort/deepthink)  │
│  routing-config.json  ← 역할→노드 가중치, QUALITY_MODE 설정      │
└────────────────────────┬────────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────────┐
│  LAYER 1: Router (hub.py action_ask 진입 전)                    │
│                                                                 │
│  Input: task_type, estimated_tokens, required_caps,            │
│         QUALITY_MODE, budget_constraint                         │
│                                                                 │
│  Gate 1: Capability Filter                                      │
│    - 파일 쓰기 필요? → cc 또는 cx (sandbox: workspace-write)    │
│    - 웹 검색 필요? → gc 또는 cx                                 │
│    - 코드 실행 필요? → gc 또는 cx                               │
│                                                                 │
│  Gate 2: Context Gate (ContextGate v1.0)                        │
│    - _estimate_tokens(query+context) vs profile.usable_context  │
│    - 초과 <10% → Pruning → 재시도                               │
│    - 초과 ≥10% → Failover to gc                                 │
│                                                                 │
│  Gate 3: Output Tier                                            │
│    - expected_output_size → required_tokens                     │
│    - required > profile.output_limit → tier 승급               │
│                                                                 │
│  Gate 4: Language                                               │
│    - CJK-heavy (>30%) + 문서 역할 → cc 우선                    │
│                                                                 │
│  Gate 5: QUALITY_MODE × Cost Sort → 최종 노드 선택             │
│    - Mode 0: cheapest capable node                              │
│    - Mode 5: min(cost × (1/quality_score))                      │
│    - Mode 10: max(quality_score) regardless of cost             │
└────────────────────────┬────────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────────┐
│  LAYER 2: Node Execution                                        │
│                                                                 │
│  선택된 Node = (peer, model, thinking_config, sandbox)          │
│  hub.py → peer CLI 호출 → 응답 수신                              │
│                                                                 │
│  실행 중 수집:                                                   │
│    - tokens_in, tokens_out, reasoning_tokens (cx API)           │
│    - latency_ms, exit_code                                      │
│    - task_type 태그 ([REFACTOR], [REVIEW], [DOC] 등)            │
└────────────────────────┬────────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────────┐
│  LAYER 3: Observer (비용 + 품질 수집)                            │
│                                                                 │
│  cost-log.jsonl 항목:                                           │
│  { ts, peer, model, thinking_config, task_type,                 │
│    tokens_in, tokens_out, reasoning_tokens,                     │
│    latency_ms, outcome, quality_signals }                       │
│                                                                 │
│  품질 프록시 (자동):                                             │
│    test_pass_rate   : pytest 결과 (0/1)                         │
│    ack_rate         : 피어 ACK / (ACK+NACK)                    │
│    output_reuse     : 다른 피어가 출력을 그대로 사용 여부        │
│    user_override    : 사용자 롤백/수정 여부 (부정 신호)          │
│                                                                 │
│  위치: _sys/data/logs/cost-log.jsonl (gitignored)               │
└────────────────────────┬────────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────────┐
│  LAYER 4: Feedback Loop (self_care.py 분석 단계)                │
│                                                                 │
│  트리거: 10 커밋 OR 누적 비용 임계값 초과                        │
│                                                                 │
│  PLAN-DO-SEE-ADJUST:                                            │
│    PLAN  → Router가 노드 선택 (routing-config.json 기반)        │
│    DO    → Node Execution                                       │
│    SEE   → Observer 수집값 분석                                  │
│             - 노드별 cost_per_success 계산                       │
│             - 노드별 failover_rate, nack_rate                   │
│    ADJUST→ proposal-add "ROUTING_UPDATE: {node} weight {Δ}"    │
│             R:8 ACK 후 routing-config.json 갱신                 │
│                                                                 │
│  cx reasoning dynamic budget:                                   │
│    실측 10회 이상 → per-effort 평균으로 static budget 대체       │
└────────────────────────┬────────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────────┐
│  LAYER 5: Registry Update (지속 업데이트 — §11 참조)            │
│                                                                 │
│  check_versions.py (주간) + hub.py 404/400 감지 (즉시)          │
│       ↓                                                         │
│  model-registry.json 변경 proposal → R:8 ACK → peers.json 파생 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 9. 비용/품질 최적화 + 피드백 루프

### 9.1 비용 추적 스키마

```jsonc
// _sys/data/logs/cost-log.jsonl (1줄 = 1 ask)
{
  "ts":               "2026-06-18T10:30:00Z",
  "session_id":       "cc-20260618-ABC1",
  "peer":             "cc",
  "model":            "claude-sonnet-4-6",
  "thinking_config":  "adaptive:medium",
  "task_type":        "IMPLEMENT",
  "tokens_in":        4200,
  "tokens_out":       1800,
  "reasoning_tokens": 0,
  "latency_ms":       3400,
  "cost_usd":         0.0396,
  "outcome":          "success",
  "quality_signals": {
    "test_pass":      true,
    "ack_rate":       1.0,
    "output_reuse":   true,
    "user_override":  false
  }
}
```

### 9.2 ROI 집계 지표

| KPI | 계산 | 목표 |
|-----|------|------|
| cost_per_success | 누적 비용 / 성공 태스크 수 | 감소 추세 |
| quality_score | (test_pass×0.4 + ack_rate×0.3 + output_reuse×0.2 + (1-override)×0.1) | ≥ 0.75 |
| failover_rate | failover 횟수 / 전체 ask 수 | < 0.05 |
| reasoning_efficiency | actual_reasoning / reserved_budget | 0.6~0.9 |
| context_utilization | avg(tokens_in / context_limit) | 0.3~0.7 |

### 9.3 세션 ROI 리포트

```
// ctx_end.py 실행 시 _archive/roi/{date}.md 자동 생성
[Session ROI Report] 2026-06-18
총 비용:   $0.42  |  성공 태스크: 12  |  cost/success: $0.035
품질 점수: 0.83   |  failover:  2회  |  override: 0회
최다 사용 노드: cc::sonnet::medium (8회, $0.21)
비용 절감 기회: R01 Router → gc::3.5-flash 전환 시 $0.08 절약 가능
```

---

## 10. QUALITY_MODE 다이얼

단일 파라미터 `QUALITY_MODE` (0~10), `_sys/ai/routing-config.json`에 저장.
COLLAB_RATE와 **직교(orthogonal)** — 독립 파라미터.

| Mode | 명칭 | 모델 티어 | Thinking/Reasoning | COLLAB_RATE 권장 | 예상 비용 |
|:----:|------|----------|-------------------|----------------|---------|
| 0 | **Budget** | standard 강제 | none / 0 / minimal | 0~3 | 최저 (~$0.05/ask) |
| 2 | **Economy** | standard 우선 | low / 1000 | 3~5 | 낮음 |
| 5 | **Balanced** | effort 우선 (기본) | medium / auto | 5 | 중간 (~$0.30/ask) |
| 7 | **Quality** | effort~deepthink | high / 12000 | 5~8 | 높음 |
| 10 | **Premium** | deepthink 강제 | max / 24576 / xhigh | 8~10 | 최고 (~$2.00/ask) |

```python
# routing-config.json
{
  "quality_mode": 5,          // 현재 설정
  "quality_mode_override": null,  // 특정 task_type별 오버라이드 가능
  "task_overrides": {
    "ESCALATION": 10,         // 에스컬레이션은 항상 Premium
    "FAST_QA":    0,          // 빠른 체크는 항상 Budget
    "IMPLEMENT":  5           // 구현은 Balanced
  }
}
```

**Mode 전환 예시 (CLI):**
```bash
python _sys/core/hub.py update-config --key quality_mode --value 7
# → routing-config.json 즉시 반영, 다음 ask부터 적용
```

---

## 11. 지속 업데이트 방안

### 11.1 파일 구조

```
_sys/ai/
  model-registry.json    ← 모든 모델 실측 스펙 SSOT (R:8 변경)
  peers.json             ← 운영 매핑 (model-registry에서 파생)
  routing-config.json    ← QUALITY_MODE, 역할→노드 가중치
_sys/checks/
  check_versions.py      ← 주간 모델 스펙 polling
_sys/data/logs/
  cost-log.jsonl         ← 세션별 비용/품질 기록 (gitignored)
  model-drift.jsonl      ← 실측값 vs 등록값 괴리 기록
```

### 11.2 model-registry.json 스키마

```jsonc
{
  "_version": "1.0",
  "_last_validated": "2026-06-18",
  "models": {
    "claude-sonnet-4-6": {
      "provider": "anthropic",
      "context_limit": 1000000,
      "output_limit": 128000,
      "reasoning_type": "adaptive",
      "reasoning_params": {"effort": ["low","medium","high","max"]},
      "temperature_supported": true,
      "vision": true,
      "tool_use": true,
      "pricing": {"input_per_1m": 3.00, "output_per_1m": 15.00},
      "status": "GA",
      "validated_at": "2026-06-18"
    }
  }
}
```

### 11.3 감지 → 검증 → 반영 파이프라인

```
[감지] Dual-Vector
  A. check_versions.py  — 주간 스케줄, 공식 /models API 폴링
  B. hub.py 인터셉트    — 404(모델 없음) / 400(파라미터 거부) 즉시 감지

        ↓

[검증] check_versions.py --validate {model_id}
  - 최소 payload 테스트 (context, output 한도 실측)
  - 파라미터 유효성 확인 (thinking, temperature 등)
  - 결과를 model-registry.json 후보 항목으로 기록

        ↓

[제안] proposal-add "MODEL_REGISTRY_UPDATE: {model_id} {field} {old}→{new}"
  - R:8 unanimous ACK 필요 (registry 변경은 헌법적 수준)

        ↓

[반영] peers.json 자동 파생
  - hub.py는 매 ask마다 peers.json 동적 로드 → 재시작 불필요

        ↓

[드리프트 감지] Observer (LAYER 3)
  - 실사용 tokens_out > registered output_limit 감지
  - reasoning_tokens 평균이 registered budget과 >20% 괴리 시
  - → model-drift.jsonl 기록 → 다음 self_care.py에서 재검증 트리거
```

### 11.4 오너십 및 권한

| 작업 | 담당 | 합의 레벨 |
|------|------|---------|
| check_versions.py 실행 | self_care.py 자동 | 자동 (exempt) |
| model-registry.json 변경 제안 | 모든 피어 가능 | proposal-add |
| model-registry.json 최종 반영 | unanimous ACK 후 자동 | **R:8** |
| peers.json 운영 매핑 변경 | 모든 피어 가능 | R:5 |
| routing-config.json 가중치 조정 | self_care.py 분석 후 제안 | R:5 |
| QUALITY_MODE 변경 | 사용자 또는 피어 | R:3 |

---

_cc+gc 끝장토론 + 3-agent web research 합의 완료 2026-06-18.
§6~11 신규 추가: 노드 아키텍처 · 역할 분류(R01~R12) · 5-레이어 라우팅 · PLAN-DO-SEE-ADJUST 피드백 루프 · QUALITY_MODE 0~10 · model-registry 지속 업데이트 파이프라인._
