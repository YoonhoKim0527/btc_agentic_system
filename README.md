# btc_agentic_system

BTC 1h 트레이딩 전략의 **에이전트(연구) 시스템** — 이 레포를 포크해서 전략/피처/모델/서치를
업그레이드하고, 고정된 **벤치마크 레포**(`btc_autoresearch`)로 점수를 받습니다.

```
[btc_agentic_system]  ← 여러분이 업그레이드 (전략, 피처, 모델, 서치 루프)
        │  Strategy 계약 (fit / positions)
        ▼
[btc_autoresearch 벤치마크]  ← 동결된 심판 (데이터, 백테스터, 비용, walk-forward,
                                인과성 게이트, sealed holdout, 리더보드)
```

## 규칙 (벤치마크가 코드로 강제)
1. 벤치마크가 walk-forward를 **직접 구동**하며 fold별로 `fit(train)` / `positions(test)`를 호출
   — 전략은 자기 분할을 고를 수 없고, 요청된 fold 너머를 볼 수 없습니다.
2. **인과성 게이트** (결정성 / future-perturbation / prefix-invariance)를 점수 전에 통과해야
   합니다. 실패 = `disqualified` (기록은 남음).
3. 비용·회계·분할은 벤치마크 상수 — 제출물이 낮출 수 없습니다.
4. **Sealed holdout은 절대 건드리지 않습니다** (벤치마크 소유의 one-shot 프로토콜).

## Setup

```bash
git clone <benchmark-repo>   # btc_autoresearch (데이터 포함 or 데이터 재생성 스크립트)
git clone <this-repo>
cd btc_agentic_system
pip install -e .             # numpy/pandas/xgboost 등
export BTC_BENCHMARK_REPO=../btc_autoresearch   # 벤치마크 체크아웃 경로
```

## 전략 계약 (v1)

```python
class MyStrategy:
    name = "my_strategy"
    horizon = 1                      # 라벨 호라이즌 선언 (purge/embargo에 사용, 리포트에 표기)

    def fit(self, data, train_start, train_end):
        # data.candles.iloc[train_start:train_end] 만 사용해 학습
        ...

    def positions(self, data, start, end):
        # t in [start, end) 의 포지션 p[t] ∈ [-1, 1] 반환.
        # p[t]는 t까지의 정보만 사용 (candles rows ≤ t; aux event_time ≤ close[t]).
        # 게이트가 검증하므로 "몰래 미래 보기"는 disqualified.
        ...
```

`data.aux`에는 funding / open_interest / mark_premium / 5m·15m·1m sub-klines 원본 프레임이
들어옵니다 (있는 경우). 인과적 사용(as-of, 완료 봉만)은 여러분 책임이고 게이트가 검사합니다.

## 실행

```bash
python -m scripts.run_benchmark --strategy agentic.strategies.ema_trend:EmaTrend
python -m scripts.run_benchmark --strategy agentic.strategies.xgb_momentum:XgbMomentum --team myteam
```

결과는 stdout + `results/leaderboard.jsonl`에 누적됩니다 (벤치마크 버전·게이트 결과 포함).

## 업그레이드 포인트
- `agentic/strategies/` — 새 전략 추가 (계약만 지키면 무엇이든: 새 피처, 모델, 멀티-호라이즌,
  레짐, 정책…)
- 자동 서치를 돌리고 싶으면 여러분의 서치 루프가 후보 전략을 만들고, **최종 후보만** 벤치마크에
  제출하세요. 제출 횟수는 리더보드에 남으며, 많이 제출할수록 결과는 선택편향으로 부풀려집니다
  (벤치마크 문서의 Deflated Sharpe 참고).

## 정직성 노트 (벤치마크 철학)
correctness > causality > robustness > honest failure > net return.
높은 수익이 누출·과적합·운 좋은 시드·숨은 비용 인하에서 왔다면 무의미합니다 — 그래서 게이트와
robustness battery(비용 배수, next-open, funding-aware, random-matched, 연도별)가 기본입니다.
