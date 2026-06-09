export type CSP = 'aws' | 'azure' | 'gcp';

export interface AssessmentFormState {
  file: File | null;
  csp: CSP | null;
  status: 'idle' | 'submitting' | 'success' | 'error';
  errorMessage: string | null;
}

export interface ValidationResult {
  valid: boolean;
  error?: string;
}
