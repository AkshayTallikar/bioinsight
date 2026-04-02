from fastapi import APIRouter, UploadFile, File, HTTPException
from services.clinvar import lookup_variants
from parsers.genomic_parser import parse_genomic_file, GenomicFileParseError

router = APIRouter()

SUPPORTED_GENOMIC_TYPES = {".txt", ".vcf"}
MAX_FILE_SIZE_BYTES = 200 * 1024 * 1024  # 200 MB (23andMe raw files can be ~25 MB)


@router.post("/upload")
async def upload_genomic_file(file: UploadFile = File(...)):
    """
    Accept a 23andMe .txt or VCF file, parse variants, and enrich via NCBI ClinVar.
    """
    filename = file.filename or ""
    suffix = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    # ── File type check ──────────────────────────────────────────────────────
    if suffix not in SUPPORTED_GENOMIC_TYPES:
        raise HTTPException(
            status_code=415,
            detail={
                "error": "unsupported_file_type",
                "message": (
                    f"'{filename}' is not a supported genomic file format. "
                    f"Only {', '.join(sorted(SUPPORTED_GENOMIC_TYPES))} files are accepted."
                ),
                "supported_formats": sorted(SUPPORTED_GENOMIC_TYPES),
                "hint": (
                    "Upload a 23andMe raw data export (.txt) or a standard VCF file (.vcf). "
                    "PDF health reports, ZIP archives, and FASTQ files are not supported."
                ),
            },
        )

    content_bytes = await file.read()

    # ── Empty file check ─────────────────────────────────────────────────────
    if len(content_bytes) == 0:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "empty_file",
                "message": "The uploaded file is empty.",
                "hint": "Ensure you exported the full raw data file from 23andMe, not just a summary.",
            },
        )

    # ── Size check ───────────────────────────────────────────────────────────
    if len(content_bytes) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail={
                "error": "file_too_large",
                "message": f"File size ({len(content_bytes) / 1_048_576:.1f} MB) exceeds the 200 MB limit.",
            },
        )

    # ── Encoding ─────────────────────────────────────────────────────────────
    try:
        text = content_bytes.decode("utf-8")
    except UnicodeDecodeError:
        try:
            text = content_bytes.decode("latin-1")
        except Exception:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "encoding_error",
                    "message": "File encoding could not be determined. Please export the file as UTF-8.",
                },
            )

    # ── Parse ────────────────────────────────────────────────────────────────
    file_type = "vcf" if suffix == ".vcf" else "23andme"
    try:
        parse_result = parse_genomic_file(text, file_type)
    except GenomicFileParseError as e:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "parse_failed",
                "message": str(e),
                "file_type_detected": file_type,
                "hint": (
                    "For 23andMe: download your raw data from Account → Settings → 23andMe Data. "
                    "For VCF: ensure the file includes the standard 8-column header."
                ),
            },
        )

    # ── ClinVar enrichment ───────────────────────────────────────────────────
    try:
        enriched = await lookup_variants(parse_result.variants)
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail={
                "error": "clinvar_lookup_failed",
                "message": f"Variants were parsed successfully but ClinVar enrichment failed: {e}",
                "hint": "Check your network connection or NCBI_API_KEY in .env",
                "variant_count": len(parse_result.variants),
            },
        )

    clinvar_hits = sum(1 for v in enriched if v.get("clinvar"))

    return {
        "variant_count": len(parse_result.variants),
        "clinvar_hits": clinvar_hits,
        "enriched": enriched,
        "parse_warnings": parse_result.warnings,
        "parse_errors": parse_result.errors,
        "skipped_lines": parse_result.skipped_lines,
    }
