# How To Run Locally

This runbook records the working local setup tested on Windows in this repo.

## Current Local Environment

Project root:

```powershell
C:\Users\delevetta\opendataloader-pdf
```

Python package and venv:

```powershell
C:\Users\delevetta\opendataloader-pdf\python\opendataloader-pdf
C:\Users\delevetta\opendataloader-pdf\python\opendataloader-pdf\.venv
```

Use the project venv through `uv run` from `python\opendataloader-pdf`, or call:

```powershell
C:\Users\delevetta\opendataloader-pdf\python\opendataloader-pdf\.venv\Scripts\python.exe
```

Observed local toolchain:

```text
Java: 24.0.1
Python: 3.12.9 system Python
uv: 0.10.11
Node: v22.22.1
npm: 10.9.4
Maven: 3.9.15 installed at C:\Users\delevetta\tools\apache-maven-3.9.15
```

`pnpm` was not installed during this setup. Node package build/test was not run.

## Important Windows Notes

The repo's npm Java build script calls `bash scripts/build-java.sh`. On this machine, `bash.exe` resolves to WSL, and WSL has no installed distro, so `npm run build-java` fails before Maven runs.

Use Maven directly from PowerShell instead.

Hugging Face model downloads failed initially because Windows symlink creation was denied. Start the hybrid server with:

```powershell
$env:HF_HUB_DISABLE_SYMLINKS = '1'
$env:HF_HUB_DISABLE_SYMLINKS_WARNING = '1'
$env:HF_HOME = Join-Path $env:TEMP 'hf-cache-opendataloader'
```

## Build Java CLI

Add Maven to the current PowerShell session:

```powershell
$env:PATH = "$env:USERPROFILE\tools\apache-maven-3.9.15\bin;$env:PATH"
```

Build the CLI jar without running tests:

```powershell
cd C:\Users\delevetta\opendataloader-pdf\java
mvn -B -DskipTests clean package -P release
```

Expected jar:

```powershell
C:\Users\delevetta\opendataloader-pdf\java\opendataloader-pdf-cli\target\opendataloader-pdf-cli-0.0.0.jar
```

The Python package build hook copies this jar into the Python package as `opendataloader-pdf-cli.jar`.

## Set Up Python Hybrid Environment

The Python package declares `readme = "README.md"`, but `python\opendataloader-pdf\README.md` is not tracked in this repo. Copy the root README temporarily before syncing.

```powershell
cd C:\Users\delevetta\opendataloader-pdf
$pkgDir = Join-Path $PWD 'python\opendataloader-pdf'
Copy-Item -Force (Join-Path $PWD 'README.md') (Join-Path $pkgDir 'README.md')
cd $pkgDir
uv sync --extra hybrid
Remove-Item -Force .\README.md
```

This installs `docling`, `easyocr`, `fastapi`, `uvicorn`, `python-multipart`, and the local `opendataloader-pdf` wrapper into:

```powershell
C:\Users\delevetta\opendataloader-pdf\python\opendataloader-pdf\.venv
```

## Enable NVIDIA GPU

The first hybrid install produced CPU-only PyTorch:

```text
torch 2.11.0+cpu
torch.cuda.is_available() = False
```

CUDA was enabled by replacing `torch` and `torchvision` inside the project venv:

```powershell
cd C:\Users\delevetta\opendataloader-pdf
uv pip install `
  --python .\python\opendataloader-pdf\.venv\Scripts\python.exe `
  --upgrade `
  --force-reinstall `
  --index-url https://download.pytorch.org/whl/cu128 `
  torch==2.11.0 `
  torchvision==0.26.0
```

Verification command:

```powershell
cd C:\Users\delevetta\opendataloader-pdf\python\opendataloader-pdf
uv run python -c "import torch; print(torch.__version__); print(torch.cuda.is_available()); print(torch.version.cuda); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'n/a')"
```

Verified output:

```text
2.11.0+cu128
True
12.8
NVIDIA RTX 2000 Ada Generation Laptop GPU
```

Do not run `uv sync` after the CUDA override unless you are prepared to reinstall the CUDA PyTorch wheels. The lock/sync flow can replace the GPU build with the CPU build again.

## Start Hybrid OCR Server

Stop any existing listener on port `5002`:

```powershell
$listener = Get-NetTCPConnection -LocalPort 5002 -ErrorAction SilentlyContinue | Select-Object -First 1
if ($listener) {
  Stop-Process -Id $listener.OwningProcess -Force -ErrorAction SilentlyContinue
}
```

Start the server with CUDA:

```powershell
cd C:\Users\delevetta\opendataloader-pdf

$env:HF_HUB_DISABLE_SYMLINKS = '1'
$env:HF_HUB_DISABLE_SYMLINKS_WARNING = '1'
$env:HF_HOME = Join-Path $env:TEMP 'hf-cache-opendataloader'
New-Item -ItemType Directory -Force -Path $env:HF_HOME | Out-Null

$pkgDir = Join-Path $PWD 'python\opendataloader-pdf'
$uv = (Get-Command uv).Source
$outLog = Join-Path $env:TEMP 'opendataloader-hybrid.out.log'
$errLog = Join-Path $env:TEMP 'opendataloader-hybrid.err.log'

Remove-Item -Force $outLog, $errLog -ErrorAction SilentlyContinue

Start-Process `
  -FilePath $uv `
  -ArgumentList @(
    'run',
    'opendataloader-pdf-hybrid',
    '--host', '127.0.0.1',
    '--port', '5002',
    '--force-ocr',
    '--ocr-lang', 'en',
    '--device', 'cuda'
  ) `
  -WorkingDirectory $pkgDir `
  -WindowStyle Hidden `
  -RedirectStandardOutput $outLog `
  -RedirectStandardError $errLog
```

Health check:

```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:5002/health
```

Expected content:

```json
{"status":"ok"}
```

Confirm GPU startup in the server log:

```powershell
Get-Content $env:TEMP\opendataloader-hybrid.err.log -Tail 80
```

Expected lines include:

```text
Accelerator: CUDA - NVIDIA RTX 2000 Ada Generation Laptop GPU (CUDA 12.8)
Device override: --device cuda
Accelerator device: 'cuda:0'
```

## Smoke Test The Backend

This is an endpoint-level diagnostic test. It calls the hybrid server directly and
does not exercise the full Java/OpenDataLoader client path, including client-side
triage, fallback, and chunking behavior.

```powershell
cd C:\Users\delevetta\opendataloader-pdf

$ErrorActionPreference = 'Stop'
$pdf = Join-Path $PWD 'samples\pdf\pdfua-1-reference-suite-1-1\PDFUA-Ref-2-09_Scanned.pdf'
$out = Join-Path $env:TEMP 'opendataloader-hybrid-response.json'
$hdr = Join-Path $env:TEMP 'opendataloader-hybrid-response.headers'

Remove-Item -Force $out, $hdr -ErrorAction SilentlyContinue

curl.exe `
  -sS `
  -D $hdr `
  -F "files=@$pdf" `
  http://127.0.0.1:5002/v1/convert/file `
  -o $out

$code = $LASTEXITCODE

if (Test-Path $out) {
  $text = Get-Content $out -Raw
  $j = $text | ConvertFrom-Json
  [pscustomobject]@{
    ExitCode = $code
    Status = $j.status
    ProcessingTime = $j.processing_time
    FailedPages = (@($j.failed_pages) -join ',')
    ErrorCount = (@($j.errors).Count)
  } | Format-List
} else {
  [pscustomobject]@{
    ExitCode = $code
    Response = 'missing'
  } | Format-List
}
```

Observed GPU-backed result:

```text
ExitCode       : 0
Status         : partial_success
ProcessingTime : 346.9372820002027
FailedPages    : 54,55,56,57,58,59,60,61,62,63,64,65,66,67,68,69,70,71,72,73,74,75,76,77,78,79,80,81,82
ErrorCount     : 35
```

The server log reported `std::bad_alloc` during preprocessing for the failed pages. That indicates memory pressure or a Docling preprocessing limitation on this 82-page scanned sample, not just missing GPU support.

The same backend endpoint succeeded for page `54` by itself and for pages `54-82`
as a range. The pages `54-82` backend request took `401.066` seconds. Its timing
breakdown was dominated by OCR:

```text
pipeline_total: 400.9583s
ocr:            399.2074s over 29 pages
page_parse:      27.8507s over 29 pages
layout:           6.7846s over 8 pages
table_structure:  3.9729s over 29 pages
```

This means the slow path observed on this sample is full-page EasyOCR work inside
the Docling backend, not curl overhead.

## Faster / Safer Test Command

The backend endpoint accepts a `page_ranges` form field. Use a small range while validating setup:

```powershell
cd C:\Users\delevetta\opendataloader-pdf

$pdf = Join-Path $PWD 'samples\pdf\pdfua-1-reference-suite-1-1\PDFUA-Ref-2-09_Scanned.pdf'
$out = Join-Path $env:TEMP 'opendataloader-hybrid-response-page1.json'

curl.exe `
  -sS `
  -F "files=@$pdf" `
  -F "page_ranges=1-1" `
  http://127.0.0.1:5002/v1/convert/file `
  -o $out
```

For large scanned PDFs, prefer chunked calls such as `1-10`, `11-20`, etc. This avoids one long request and reduces the chance of preprocessing memory failures.

## Client Wrapper Command

Once the server is running, use the Python wrapper or CLI with `--hybrid docling-fast`:

```powershell
cd C:\Users\delevetta\opendataloader-pdf\python\opendataloader-pdf
uv run opendataloader-pdf --hybrid docling-fast C:\path\to\file.pdf
```

For enrichment features such as formula extraction or picture descriptions, the client must also use:

```powershell
--hybrid-mode full
```

## Native Java Client Test

This command exercises the normal OpenDataLoader Java client path against the
running hybrid server:

```powershell
cd C:\Users\delevetta\opendataloader-pdf

$pdf = Join-Path $PWD 'samples\pdf\pdfua-1-reference-suite-1-1\PDFUA-Ref-2-09_Scanned.pdf'
$outDir = Join-Path $env:TEMP 'opendataloader-native-hybrid-54-82'
$jar = Join-Path $PWD 'java\opendataloader-pdf-cli\target\opendataloader-pdf-cli-0.0.0.jar'

Remove-Item -Recurse -Force $outDir -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

java -jar $jar `
  --hybrid docling-fast `
  --hybrid-url http://127.0.0.1:5002 `
  --hybrid-mode full `
  --pages 54-82 `
  --format json `
  --output-dir $outDir `
  $pdf
```

Observed result:

```text
Output:
C:\Users\delevetta\AppData\Local\Temp\opendataloader-native-hybrid-54-82\PDFUA-Ref-2-09_Scanned.json

Backend log:
Finished converting document tmpy8jls0gp.pdf in 371.89 sec.
```

For pages `54-82`, the native Java client and the direct backend diagnostic are
in the same performance range: about `372-401` seconds for 29 pages. That points
to the Docling/EasyOCR backend conversion as the bottleneck, not the command
wrapper.

## Testing Done During Setup

Completed:

- Installed Maven 3.9.15 under `C:\Users\delevetta\tools\apache-maven-3.9.15`.
- Built the Java CLI jar with `mvn -B -DskipTests clean package -P release`.
- Synced the Python hybrid environment with `uv sync --extra hybrid`.
- Replaced CPU-only PyTorch with CUDA PyTorch in the project venv.
- Verified `torch.cuda.is_available()` is `True`.
- Started `opendataloader-pdf-hybrid` on `127.0.0.1:5002` with `--device cuda`.
- Verified `/health` returned `{"status":"ok"}`.
- Ran `/v1/convert/file` against `PDFUA-Ref-2-09_Scanned.pdf`.
- Ran the native Java CLI with `--hybrid docling-fast --hybrid-mode full --pages 54-82`; it wrote JSON successfully and the backend conversion took `371.89` seconds.

Not completed:

- Full Java tests were not used as the final verification path. `mvn -B clean package -P release` was attempted first and returned non-zero after a long test run with extensive PDF processing warnings.
- Node package setup/build/test was not run because `pnpm` was not installed.
- A full 82-page scanned-PDF OCR run did not complete with full success. It returned `partial_success` with `std::bad_alloc` on later pages.
