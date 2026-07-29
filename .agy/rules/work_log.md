# AI Work Logging Rule

**Trigger**: This rule must be followed for **EVERY** task or request processed by the AI in this project.

**Action**:
At the beginning or end of your task execution, you MUST:
1. Append a log entry to a persistent work log file in the project's root directory.
2. **Update `SmartVideoCompressor_Specification.txt`** in the project's root directory to reflect any new features, changed algorithms, fixed bugs, or UI changes. The specification must always reflect the current state of the app.

**File Naming**:
The log file must be named `AI_Work_Log_YYYYMMDD_HH.txt` (e.g., `AI_Work_Log_20260728_09.txt`), rotating every hour.

**Specification Update Rules** (`SmartVideoCompressor_Specification.txt`):
- Update the relevant section(s) that correspond to the change made.
- For algorithm changes: describe the old logic, what caused the problem, and the new logic/fix.
- For UI changes: describe what was added, changed, or removed from the interface.
- For bug fixes: record the root cause and the exact solution applied.
- Always update the 최종 업데이트 일자 (last updated date) at the top.
- Do NOT rewrite unrelated sections; only update the sections that changed.

**Format and Content**:
You must append (누가 기록) the following details for every task, strictly following this format:

==================================================
[작업 기록] YYYY-MM-DD HH:MM:SS
==================================================
* 대상 파일: (수정 또는 대상이 된 파일명과 버전)
* AI 모델: (현재 사용 중인 AI 모델명, 예: Gemini 3.1 Pro High)
* 작업 목적: (해당 작업의 목표와 배경)
* 작업 절차 및 알고리즘 수정 상세:
  1. (단계 1 절차 및 구체적으로 어떤 알고리즘/로직을 어떻게 수정했는지/할 것인지)
  2. (단계 2 절차 및 구체적으로 어떤 알고리즘/로직을 어떻게 수정했는지/할 것인지)
  ...
* Specification 갱신: (갱신한 섹션 및 내용 요약, 또는 '해당 없음')
