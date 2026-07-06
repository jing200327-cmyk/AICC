# Fullstack Handoff

## Audit Summary

- Backend: Python FastAPI in `glm-proxy/server.py`.
- Frontend: React 18 + Vite + TypeScript + Tailwind in `frontend`.
- Package managers: `pip` for backend virtualenv, `npm` for frontend.
- Backend tests: `pytest`.
- Frontend tests: `vitest` + Testing Library.
- Frontend build: `npm run build`.
- Frontend lint: `npm run lint`.

## Paths

- Backend entry: `glm-proxy/server.py`
- Backend lead import modules: `glm-proxy/lead_import`
- Backend tests: `glm-proxy/tests/test_lead_import.py`
- Frontend entry: `frontend/src/main.tsx`
- Frontend page: `frontend/src/pages/LeadImportPage.tsx`
- Frontend API client: `frontend/src/api/leadImportClient.ts`
- Frontend tests: `frontend/src/components/__tests__/leadImportUi.test.tsx`
- Store scripts: `线索变量脚本`
- Default output: `glm-proxy/outputs/lead-import/{store_code}/{yyyyMMdd}/{job_id}.txt`

## Environment Variables

- `LEAD_IMPORT_OUTPUT_DIR`: optional backend output root.
- `LEAD_IMPORT_INPUT_DIR`: optional backend upload root.
- `GLM_PROXY_PORT`: optional backend port, default `18765`.
- `GLM_PROXY_MODEL`: optional GLM proxy model.
- `VITE_API_BASE_URL`: optional frontend API base URL. Dev mode normally uses Vite `/api` proxy.

## Start Commands

Backend:

```powershell
cd E:\ai\workflow\线索变量脚本\glm-proxy
.\venv\Scripts\python.exe server.py --port 18765
```

Frontend:

```powershell
cd E:\ai\workflow\线索变量脚本\frontend
npm run dev -- --host 127.0.0.1 --port 3000
```

If port `3000` is occupied, choose another port. In this environment, `/index.html` was the verified dev entry for the Vite server used during handoff.

## Test Commands

Backend:

```powershell
cd E:\ai\workflow\线索变量脚本
.\glm-proxy\venv\Scripts\python.exe -m pytest .\glm-proxy\tests -q
```

Frontend:

```powershell
cd E:\ai\workflow\线索变量脚本\frontend
npm test
npm run lint
npm run build
```

## Verified Results

- Backend tests: `9 passed`.
- Frontend tests: `6 passed`.
- Frontend lint: passed.
- Frontend production build: passed.
- Full upload-to-download integration: passed with a desensitized workbook named `武汉银马-脱敏测试.xlsx`.
- Generated txt path returned by backend:
  `glm-proxy/outputs/lead-import/wuhan_yinma/20260703/job_20260703_bdb891e4eae8.txt`
- Download verification: passed, downloaded txt contained the expected JSON line for `武汉银马店`.

## Known Risks

- Some legacy store scripts contain mojibake and hard-coded historical paths. The API uses a registry wrapper and does not execute client-provided script paths.
- The existing GLM proxy file still contains a hard-coded API key fallback from earlier project state. This should be moved to environment-only configuration in a separate security task.
- A pre-existing Python process continued listening on `127.0.0.1:18765` after verification and could not be stopped from this sandbox.
