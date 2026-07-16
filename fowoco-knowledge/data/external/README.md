# External data

공식 원본 데이터는 이 디렉토리에 커밋하지 않습니다. 출처·버전·원본 해시는
`source_manifest.yaml`, 제조업 정규화 결과는 `data/processed/`에서 관리합니다.

1. `knowledge/official_links.yaml`의 출처에서 원본 다운로드
2. 라이선스·게시일·행 수 확인
3. `local-data/official/`에서 SHA·행 수·컬럼 검증
4. `sync-official-data`로 제조업 정규화 스냅샷 생성
5. Knowledge 변경 Issue와 Pull Request에 확인일·변환 규칙 기록

이 방식은 원본 데이터 재배포와 오래된 스냅샷의 무분별한 사용을 방지합니다. 세부 기준은
`docs/OFFICIAL_DATA_PIPELINE.md`를 확인합니다.
