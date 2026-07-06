# Lead Import Business Rules

## Store Detection

The backend, not the frontend, decides which store script may run.

Detection uses these signals:

1. Original uploaded filename keywords.
2. Excel sheet names.
3. Column names.
4. Sampled content keywords from the first rows.

Filename matches carry enough confidence to route files such as `武汉银马-线索.xlsx` directly to the Wuhan Yinma store folder. If confidence is still below the threshold, the job returns `need_confirmation`; retrying with `force_store_code` is allowed only for registered stores.

## File Storage

The API never accepts a user-supplied script path or output directory.

Default storage root:

`E:\ai\workflow\线索变量脚本\建银线索`

Runtime override:

`LEAD_IMPORT_INPUT_DIR`

Saved file pattern:

`{storage_root}/{门店文件夹}/{job_id}_{original_filename}`

Generated txt pattern:

`{storage_root}/{门店文件夹}/{job_id}_{original_file_stem}.txt`

## Allowed File Types

Allowed upload extensions:

- `.xlsx`
- `.xls`
- `.csv`

Unsupported formats are rejected before processing.

## TXT Record Rules

Each generated line is a compact JSON object:

- `carNo`: vehicle plate formatted as first character + `.` + remaining characters.
- `carType`: first matched model/series column.
- `last_maintain_mileage`: first matched mileage column, normalized as text.
- `last_maintain_time`: first matched date/time column, normalized to `YYYY-MM-DD`.
- `advised_maintain_time`: `last_maintain_time + 6 months`.
- `duration`: fixed `"6"`.
- `powerType`: fixed `"油车"`.
- `assigned_store`: registry store name.

## Legacy Script Boundaries

Existing store scripts are preserved as business-rule references. The API wrapper does not expose arbitrary script paths, arbitrary output paths, or direct subprocess execution from client input.
