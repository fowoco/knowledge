# ADR-0001: GitHub Flow 기반 모노레포 운영

- Status: Accepted
- Date: 2026-07-16
- Decision owners: FOWOCO 14조
- Related issues: #9

## Context

7명이 짧은 프로젝트 기간에 Client, Server, AI, Knowledge, Infra를 병렬 개발해야 합니다.
장기 `develop` 브랜치를 두면 `main`과의 동기화, 릴리스 브랜치 관리, 충돌 해결 비용이 증가합니다.

## Decision

- `main`을 유일한 통합 기준으로 사용
- Issue 기반의 짧은 기능 브랜치와 Draft PR 사용
- 모노레포 안에서 패키지별 책임을 분리하고 계약으로 연결
- CI 통과와 리뷰 후 Squash 또는 Rebase 방식으로 병합
- 병합 후 기능 브랜치 자동 삭제

## Alternatives

- Git Flow: 릴리스가 여러 개 병행되지 않는 학생 프로젝트에 관리 비용이 큼
- 패키지별 다중 저장소: 초기 계약 변경이 잦아 동기화와 Issue 추적이 어려움
- `main` 직접 커밋: 변경 추적과 리뷰, CI 게이트를 적용할 수 없음

## Consequences

### Positive

- 팀 전체 변경과 연동 상태를 한 PR에서 추적 가능
- 충돌을 조기에 발견하고 작은 단위로 병합 가능
- Issue·Milestone·CI를 하나의 프로젝트 흐름으로 사용 가능

### Negative

- 패키지 경계를 지키지 않으면 큰 PR이 생길 수 있음
- 경로별 CI와 명시적인 API·Schema 계약 관리가 필요

## Validation

- PR 평균 리드타임 3일 이하
- 기능 PR의 변경 목적 1개 유지
- `main` CI 실패 병합 0건
- 패키지 간 계약 오류를 통합 전 CI에서 탐지
