'use client';

import { useState, useRef, DragEvent, ChangeEvent } from 'react';
import { validateFile } from '@/lib/validation';

interface FileUploadProps {
  onFileChange: (file: File | null) => void;
}

export default function FileUpload({ onFileChange }: FileUploadProps) {
  const [dragActive, setDragActive] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const processFile = (file: File) => {
    const result = validateFile(file);
    if (!result.valid) {
      setValidationError(result.error!);
      setSelectedFile(null);
      onFileChange(null);
      return;
    }
    setValidationError(null);
    setSelectedFile(file);
    onFileChange(file);
  };

  const handleDrag = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') setDragActive(true);
    else if (e.type === 'dragleave') setDragActive(false);
  };

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files[0]) processFile(e.dataTransfer.files[0]);
  };

  const handleChange = (e: ChangeEvent<HTMLInputElement>) => {
    if (e.target.files?.[0]) processFile(e.target.files[0]);
  };

  const clearFile = () => {
    setSelectedFile(null);
    setValidationError(null);
    onFileChange(null);
    if (inputRef.current) inputRef.current.value = '';
  };

  return (
    <div>
      <div
        className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors
          ${dragActive ? 'border-blue-500 bg-blue-50' : 'border-gray-300 hover:border-gray-400'}
          ${validationError ? 'border-red-400 bg-red-50' : ''}
        `}
        onDragEnter={handleDrag}
        onDragOver={handleDrag}
        onDragLeave={handleDrag}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
        role="button"
        aria-label="Upload file"
      >
        <input
          ref={inputRef}
          type="file"
          className="hidden"
          accept=".pdf,.docx,.xlsx,.csv"
          onChange={handleChange}
          data-testid="file-input"
        />

        {selectedFile ? (
          <div className="flex items-center justify-center gap-3">
            <svg className="w-5 h-5 text-green-500 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span className="text-gray-700 font-medium truncate max-w-xs">{selectedFile.name}</span>
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); clearFile(); }}
              className="text-sm text-red-500 hover:text-red-700 underline shrink-0"
              aria-label="Remove file"
            >
              Remove
            </button>
          </div>
        ) : (
          <div className="space-y-1">
            <svg className="w-10 h-10 text-gray-400 mx-auto" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 13h6m-3-3v6m5 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            <p className="text-gray-600">
              <span className="font-semibold text-blue-600">Click to upload</span> or drag &amp; drop
            </p>
            <p className="text-sm text-gray-400">PDF, DOCX, XLSX, CSV &middot; Max 25 MB</p>
          </div>
        )}
      </div>

      {validationError && (
        <p className="mt-2 text-sm text-red-600" role="alert">{validationError}</p>
      )}
    </div>
  );
}
