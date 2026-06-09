import type { ValidationResult } from './types';

const ALLOWED_EXTENSIONS = new Set(['.pdf', '.docx', '.xlsx', '.csv']);
const MAX_SIZE_BYTES = 25 * 1024 * 1024;

export function validateFile(file: File): ValidationResult {
  const dotIndex = file.name.lastIndexOf('.');
  const ext = dotIndex !== -1 ? file.name.slice(dotIndex).toLowerCase() : '';

  if (!ALLOWED_EXTENSIONS.has(ext)) {
    return {
      valid: false,
      error: 'Unsupported file type. Please upload a PDF, DOCX, XLSX, or CSV file.',
    };
  }

  if (file.size > MAX_SIZE_BYTES) {
    return {
      valid: false,
      error: 'File exceeds the 25 MB size limit.',
    };
  }

  return { valid: true };
}
