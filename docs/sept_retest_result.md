# 9월 재검사 결과 (intra-annotator)

입력 파일: `data/labels/goldset_retest_sept.xlsx` · 원본: `data/labels/goldset_labeled_v2.csv`

표본 60건은 8월 재검사(60건)와 **겹치지 않는다**. G0106·G0136 은 docs/22 §4.3 에서 식별자가 저자에게 노출된 이력이 있어 (편차 로그 P-2026-08-20-5), 전체 60건과 이 둘을 제외한 58건을 모두 보고한다.

## L1 (위임/인용/판단불가)

```
  n = 60 · 관측일치도 100.0% (60/60)
  Cohen κ = 1.000 · PABAK = 1.000 · Gwet AC1 = 1.000 · κ 부트스트랩 95% CI [1.000, 1.000] (유효 1749)
  불일치 없음
  n = 58 · 관측일치도 100.0% (58/58)
  Cohen κ = 1.000 · PABAK = 1.000 · Gwet AC1 = 1.000 · κ 부트스트랩 95% CI [1.000, 1.000] (유효 1727)
  불일치 없음
```

## L2 — 등록 기준(집합 교집합), 원본 주형식∪병존형식(v1.1 `goldset_labeled_v2.csv`) vs 재검사 '|' 병기

```
  n = 58 · 관측일치도 100.0% (58/58)
  정렬집합 κ (교집합 기준; 표준 Cohen κ 아님) = 1.000 · PABAK = 1.000 · Gwet AC1 = 1.000 · κ 부트스트랩 95% CI [1.000, 1.000] (유효 2000)
  불일치 없음
  n = 56 · 관측일치도 100.0% (56/56)
  정렬집합 κ (교집합 기준; 표준 Cohen κ 아님) = 1.000 · PABAK = 1.000 · Gwet AC1 = 1.000 · κ 부트스트랩 95% CI [1.000, 1.000] (유효 2000)
  불일치 없음
```

## L2 — 정확일치(병기 참고값)

```
  n = 58 · 관측일치도 96.6% (56/58)
  Cohen κ = 0.953 · PABAK = 0.962 · Gwet AC1 = 0.962 · κ 부트스트랩 95% CI [0.878, 1.000] (유효 2000)
  불일치:
    G0070  8월 '대통령령|조례'  →  9월 '조례'
    G0188  8월 '조례|학칙'  →  9월 '조례'
  n = 56 · 관측일치도 96.4% (54/56)
  Cohen κ = 0.951 · PABAK = 0.960 · Gwet AC1 = 0.961 · κ 부트스트랩 95% CI [0.872, 1.000] (유효 2000)
  불일치:
    G0070  8월 '대통령령|조례'  →  9월 '조례'
    G0188  8월 '조례|학칙'  →  9월 '조례'
```

## 지표 해석

L1 은 원본 분포가 극단적으로 치우쳐 있어(위임 58 / 인용 2) Cohen κ 가 유병률 역설에 취약하다. 그래서 관측일치도·PABAK·Gwet AC1 을 함께 적는다. **주 보고값은 등록대로 Cohen κ 이고 나머지는 기술통계**다.

## 원고 문장

> The re-test was completed on 2026-09-06, 22 days after the original labelling — beyond the registered three-week minimum, though two days before the calendar date named in the registration (recorded in the deviation log). On the fresh 60-item sample the author reproduced the original L1 labels on 100.0% of items (Cohen's κ = 1.00, PABAK = 1.00); over the 58 items both passes classify as delegations, L2 agreement was 96.6% (κ = 0.95), the two divergent items reproducing the primary form but omitting a co-listed second form. Excluding the two items whose identifiers appeared in a public adjudication note before the re-test, L1 agreement over the remaining 58 was 100.0% (Cohen's κ = 1.00). L2 is compared as form sets, co-listed forms included. Every re-test label is released alongside the original.
