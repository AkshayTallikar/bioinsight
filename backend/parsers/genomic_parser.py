"""
Parse genomic files and extract clinically relevant variant rs# IDs.

Supports:
  - 23andMe raw data (.txt)  — tab-separated: rsid, chromosome, position, genotype
  - VCF (.vcf)               — standard VCF format, extracts rs# from ID column

Error handling:
  - Detects wrong file types masquerading as genomic files
  - Validates minimum structure (columns, rs# prefix)
  - Reports parse warnings without crashing
  - Caps at MAX_VARIANTS to avoid hammering ClinVar with 600k+ SNPs
"""

from __future__ import annotations

from dataclasses import dataclass, field

MAX_VARIANTS = 2000
MIN_CONTENT_LINES = 2  # At least one comment + one data line expected


class GenomicFileParseError(Exception):
    """Raised when the genomic file cannot be parsed at all."""


@dataclass
class GenomicParseResult:
    variants: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    errors: list = field(default_factory=list)
    total_lines: int = 0
    skipped_lines: int = 0
    file_type: str = ""


def parse_genomic_file(content: str, file_type: str) -> GenomicParseResult:
    """
    Parse a genomic file and return variants with parse metadata.

    Args:
        content: decoded file text
        file_type: 'vcf' or '23andme'

    Returns:
        GenomicParseResult with variants + warnings/errors

    Raises:
        GenomicFileParseError for fatal structural issues
    """
    if not content.strip():
        raise GenomicFileParseError("File is empty.")

    lines = content.splitlines()
    if len(lines) < MIN_CONTENT_LINES:
        raise GenomicFileParseError(
            f"File has only {len(lines)} line(s) — too short to be a valid genomic file."
        )

    # Sniff file type consistency
    _validate_file_type_match(lines, file_type)

    if file_type == "23andme":
        return _parse_23andme(lines)
    elif file_type == "vcf":
        return _parse_vcf(lines)
    else:
        raise GenomicFileParseError(
            f"Unknown file type '{file_type}'. Supported types: 23andme (.txt), vcf (.vcf)."
        )


def _validate_file_type_match(lines: list[str], file_type: str) -> None:
    """Detect obvious mismatches — e.g. a CSV uploaded as a VCF."""
    data_lines = [l for l in lines if l.strip() and not l.startswith("#")]
    if not data_lines:
        raise GenomicFileParseError(
            "File contains only comment/header lines and no data."
        )

    sample = data_lines[0]

    if file_type == "vcf":
        parts = sample.split("\t")
        if len(parts) < 5:
            # Could be comma-separated or completely wrong format
            if "," in sample:
                raise GenomicFileParseError(
                    "File appears to be comma-separated (CSV), not a VCF. "
                    "VCF files use tab-separated columns: CHROM, POS, ID, REF, ALT, ..."
                )
            raise GenomicFileParseError(
                f"File does not look like a VCF — expected ≥5 tab-separated columns, "
                f"got {len(parts)} in first data row."
            )

    elif file_type == "23andme":
        parts = sample.split("\t")
        if len(parts) < 4:
            if "," in sample:
                raise GenomicFileParseError(
                    "File appears to be comma-separated (CSV), not a 23andMe export. "
                    "23andMe raw data files use tab-separated columns: rsid, chromosome, position, genotype."
                )
            raise GenomicFileParseError(
                f"File does not look like a 23andMe export — expected 4 tab-separated columns "
                f"(rsid, chromosome, position, genotype), got {len(parts)} in first data row."
            )


def _parse_23andme(lines: list[str]) -> GenomicParseResult:
    result = GenomicParseResult(file_type="23andme")
    result.total_lines = len(lines)
    data_lines = [l for l in lines if l.strip() and not l.startswith("#")]

    if not data_lines:
        raise GenomicFileParseError("23andMe file contains no data rows (only comments).")

    for i, line in enumerate(data_lines, start=1):
        parts = line.split("\t")

        if len(parts) < 4:
            result.warnings.append(
                f"Line {i}: Expected 4 columns, got {len(parts)} — skipped."
            )
            result.skipped_lines += 1
            continue

        rsid, chrom, pos, genotype = parts[0].strip(), parts[1].strip(), parts[2].strip(), parts[3].strip()

        if not rsid.startswith("rs"):
            result.skipped_lines += 1
            continue  # Non-rs IDs (e.g. mitochondrial) — silently skip, not an error

        if not pos.isdigit():
            result.warnings.append(f"Line {i}: Non-numeric position '{pos}' for {rsid} — skipped.")
            result.skipped_lines += 1
            continue

        if genotype in ("--", "NN", ""):
            result.skipped_lines += 1
            continue  # No-call — normal, skip silently

        result.variants.append({
            "rsid": rsid,
            "chromosome": chrom,
            "position": pos,
            "genotype": genotype,
        })

        if len(result.variants) >= MAX_VARIANTS:
            result.warnings.append(
                f"Variant cap of {MAX_VARIANTS} reached — remaining variants skipped to limit API calls."
            )
            break

    if not result.variants:
        raise GenomicFileParseError(
            "No valid rs# variants could be extracted from the 23andMe file. "
            "Ensure the file is a raw data export (not a health report PDF)."
        )

    return result


def _parse_vcf(lines: list[str]) -> GenomicParseResult:
    result = GenomicParseResult(file_type="vcf")
    result.total_lines = len(lines)
    data_lines = [l for l in lines if l.strip() and not l.startswith("#")]

    if not data_lines:
        raise GenomicFileParseError("VCF file contains no data rows (only header/meta lines).")

    for i, line in enumerate(data_lines, start=1):
        parts = line.split("\t")

        if len(parts) < 5:
            result.warnings.append(
                f"VCF row {i}: Expected ≥5 columns, got {len(parts)} — skipped."
            )
            result.skipped_lines += 1
            continue

        chrom, pos, rsid, ref, alt = (
            parts[0].strip(), parts[1].strip(), parts[2].strip(),
            parts[3].strip(), parts[4].strip(),
        )

        if not rsid.startswith("rs"):
            result.skipped_lines += 1
            continue  # Novel/unnamed variants — skip

        if not pos.isdigit():
            result.warnings.append(f"VCF row {i}: Non-numeric POS '{pos}' for {rsid} — skipped.")
            result.skipped_lines += 1
            continue

        if ref == "." or alt == ".":
            result.skipped_lines += 1
            continue  # Missing allele data

        result.variants.append({
            "rsid": rsid,
            "chromosome": chrom,
            "position": pos,
            "ref": ref,
            "alt": alt,
        })

        if len(result.variants) >= MAX_VARIANTS:
            result.warnings.append(
                f"Variant cap of {MAX_VARIANTS} reached — remaining variants skipped to limit API calls."
            )
            break

    if not result.variants:
        raise GenomicFileParseError(
            "No rs# variants found in the VCF file. "
            "Only variants with rs# identifiers in the ID column are processed."
        )

    return result
