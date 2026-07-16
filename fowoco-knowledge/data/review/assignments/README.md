# 독립 검수 배정

- 검수 시작 전 [`docs/REVIEWER_GUIDE_KO.md`](../../../docs/REVIEWER_GUIDE_KO.md)를 읽고,
  [`label_reference.csv`](../label_reference.csv)를 영문 태그·한글 의미 참조표로 사용합니다.
- `reviewer_a.csv`와 `reviewer_b.csv`는 동일한 40개 Seed를 서로 독립적으로 검수하는 파일입니다.
- 검수자는 상대 파일을 열거나 기존 `gold_seed.csv`의 제안 라벨을 확인하지 않습니다.
- `decision`은 `APPROVE`, `CORRECT`, `REJECT`, `EXPERT_REVIEW` 중 하나를 사용합니다.
- Intent·Domain 분류는 팀 합의로 확정할 수 있지만, 고위험 Workflow·필수서류·조치안은
  전문가 검수 전 정답으로 사용하지 않습니다.
- 완성 파일은 데이터 담당자가 회수해 `adjudication_template.csv`에서 합의합니다.

영문 태그만 CSV에 입력하고, 한글 설명은 의미 확인용으로만 사용합니다. 복수 태그는
쉼표가 아니라 `|`로 구분합니다.
