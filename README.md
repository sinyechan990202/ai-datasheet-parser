# 데이터시트 → RTL 인터페이스 어시스턴트

외부 칩 데이터시트(`datasheets/`)를 계층형 파싱(Tier0 텍스트 → Tier1 표 → Tier2 Vision)으로 처리해 벡터DB에 인덱싱하고, RAG 에이전트로 질의응답하는 로컬 미니 프로젝트. 설계 배경과 트레이드오프는 `STORYTELLING_FRAMEWORK.md` 참고.

## 구조

```
datasheets/          실제 데이터시트 PDF (칩별 폴더)
src/parsing/          Tier0(텍스트)·Tier1(표)·vision_router(라우팅)·Tier2(Vision) → pipeline.py 오케스트레이션
src/vectordb/         임베딩(sentence-transformers, 로컬) + Chroma 인덱스 빌드
src/agent/            Claude tool-use RAG 에이전트, 질의 로그(query_log.jsonl) 기록
src/dashboard/        Streamlit 대시보드 (질의응답 + 통계)
decision_log.md        설계 결정 기록 (자소서 5단계 재료)
```

## 준비

1. `pip install -r requirements.txt`
2. `.env.example`을 `.env`로 복사하고 `ANTHROPIC_API_KEY`에 본인 키를 입력 (`CLAUDE_API_KEY_YECHAN.txt`에 있는 키를 그대로 옮기면 됨)

## 실행

```bash
# 1. 파싱 + 인덱싱 (Tier0/1/2 실행 후 Chroma에 저장)
python -m src.vectordb.build_index

# 2. 대시보드 실행
streamlit run src/dashboard/app.py
```

`build_index`는 `datasheets/` 아래 모든 PDF를 재귀적으로 찾아 처리한다. Vision(Tier2)이 호출된 페이지 수가 로그에 출력되므로, 이 값으로 `STORYTELLING_FRAMEWORK.md`의 커버율/절감률을 계산할 수 있다.

## 검증 (Recall@k)

`decision_log.md`의 안내에 따라 테스트 질문 세트를 만들고 정답 페이지를 라벨링한 뒤, `_search()`가 top-k에 정답을 포함하는 비율을 계산해 채워 넣는다.
