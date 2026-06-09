'use client';

import { useState } from 'react';
import type { AssessmentFormState, CSP } from '@/lib/types';
import FileUpload from './FileUpload';
import CSPSelector from './CSPSelector';
import StatusBanner from './StatusBanner';

export default function AssessmentForm() {
  const [state, setState] = useState<AssessmentFormState>({
    file: null,
    csp: null,
    status: 'idle',
    errorMessage: null,
  });

  const canSubmit = state.file !== null && state.csp !== null && state.status !== 'submitting';

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSubmit) return;

    setState((s) => ({ ...s, status: 'submitting', errorMessage: null }));

    try {
      const body = new FormData();
      body.append('file', state.file!);
      body.append('csp', state.csp!);

      const res = await fetch('/api/assess', { method: 'POST', body });

      if (!res.ok) {
        const json = await res.json().catch(() => ({}));
        throw new Error(json.message ?? `Server error ${res.status}`);
      }

      setState((s) => ({ ...s, status: 'success' }));
    } catch (err) {
      setState((s) => ({
        ...s,
        status: 'error',
        errorMessage: err instanceof Error ? err.message : 'Submission failed. Please try again.',
      }));
    }
  };

  const resetStatus = () => setState((s) => ({ ...s, status: 'idle', errorMessage: null }));

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Portfolio Document
        </label>
        <FileUpload
          onFileChange={(file) => { setState((s) => ({ ...s, file })); resetStatus(); }}
        />
      </div>

      <CSPSelector
        value={state.csp}
        onChange={(csp: CSP) => { setState((s) => ({ ...s, csp })); resetStatus(); }}
      />

      {state.status === 'success' && (
        <StatusBanner
          status="success"
          message="Assessment submitted successfully. Results will appear shortly."
        />
      )}

      {state.status === 'error' && state.errorMessage && (
        <StatusBanner status="error" message={state.errorMessage} />
      )}

      <button
        type="submit"
        disabled={!canSubmit}
        className={`w-full py-3 px-6 rounded-xl font-semibold text-sm transition-all duration-150
          ${canSubmit
            ? 'bg-blue-600 hover:bg-blue-700 active:scale-[0.99] text-white shadow-sm'
            : 'bg-gray-200 text-gray-400 cursor-not-allowed'
          }
        `}
      >
        {state.status === 'submitting' ? (
          <span className="flex items-center justify-center gap-2">
            <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
            </svg>
            Submitting…
          </span>
        ) : (
          'Start Assessment'
        )}
      </button>
    </form>
  );
}
