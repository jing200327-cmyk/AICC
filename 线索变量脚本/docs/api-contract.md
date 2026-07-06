# Lead Import API Contract

## Base URL

Default local base URL: `http://127.0.0.1:18765`

## POST /api/leads/import

Upload a lead file and create a processing job.

Request type: `multipart/form-data`

Fields:

- `file`: required. Supported extensions: `.xlsx`, `.xls`, `.csv`.
- `remark`: optional string.
- `force_store_code`: optional string. Must exist in the server-side store registry.

Behavior:

- The backend detects the store from the original upload filename, sheet names, columns, and sampled cell content.
- The frontend cannot pass script paths or output directories.
- After store detection, the upload is saved under `E:\ai\workflow\线索变量脚本\建银线索\{门店文件夹}`.
- The generated txt is written to the same store folder and returned in the job detail as `output.txt_preview`.

Success response:

```json
{
  "job_id": "job_20260703_abcdef123456",
  "status": "completed",
  "message": "Lead import completed"
}
```

## GET /api/leads/import/jobs/{job_id}

Return job status and processing details.

```json
{
  "job_id": "job_20260703_abcdef123456",
  "status": "completed",
  "detected_store": {
    "store_code": "wuhan_yinma",
    "store_name": "武汉银马店",
    "confidence": 0.95,
    "matched_by": ["filename"]
  },
  "candidate_stores": [],
  "input_file": {
    "filename": "武汉银马-线索.xlsx",
    "size": 123456,
    "saved_path": "E:\\ai\\workflow\\线索变量脚本\\建银线索\\武汉银马\\job_20260703_abcdef123456_武汉银马-线索.xlsx"
  },
  "output": {
    "txt_file_path": "E:\\ai\\workflow\\线索变量脚本\\建银线索\\武汉银马\\job_20260703_abcdef123456_武汉银马-线索.txt",
    "download_url": "/api/leads/import/jobs/job_20260703_abcdef123456/download",
    "txt_preview": "{\"carNo\":\"鄂.A12345\"}\n"
  },
  "logs": ["Upload received", "Saved to store folder", "TXT generated: 1 records"],
  "error": null,
  "created_at": "2026-07-03T10:30:00+08:00",
  "updated_at": "2026-07-03T10:30:02+08:00"
}
```

## GET /api/leads/import/jobs/{job_id}/download

Download the generated txt file.

Responses:

- `200`: `text/plain; charset=utf-8` file response.
- `404`: `JOB_NOT_FOUND` or `DOWNLOAD_FILE_NOT_FOUND`.
- `409`: `JOB_NOT_COMPLETED`.

## GET /api/leads/import/stores

Return registered and allowlisted store scripts.

```json
{
  "stores": [
    {
      "store_code": "wuhan_yinma",
      "store_name": "武汉银马店",
      "city": "武汉",
      "brand": "马自达",
      "keywords": ["武汉银马", "银马"],
      "folder_name": "武汉银马",
      "call_mode": "registry_wrapper"
    }
  ]
}
```

## Error Shape

```json
{
  "error": {
    "code": "STRING_CODE",
    "message": "Human readable message",
    "detail": "Optional diagnostic detail"
  }
}
```

Common codes: `EMPTY_FILE`, `UNSUPPORTED_FILE_TYPE`, `FILE_TOO_LARGE`, `INVALID_STORE_CODE`, `STORE_DETECTION_LOW_CONFIDENCE`, `SCRIPT_EXECUTION_FAILED`, `OUTPUT_WRITE_FAILED`, `JOB_NOT_FOUND`, `DOWNLOAD_FILE_NOT_FOUND`.
