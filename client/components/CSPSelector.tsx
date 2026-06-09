'use client';

import { CSP } from '@/lib/types';

interface CSPSelectorProps {
  value: CSP | null;
  onChange: (csp: CSP) => void;
}

const CSP_OPTIONS: {
  id: CSP;
  label: string;
  shortName: string;
  description: string;
  activeClasses: string;
  badge: string;
}[] = [
  {
    id: 'aws',
    label: 'Amazon Web Services',
    shortName: 'AWS',
    description: 'EC2, ECS, RDS, Lambda',
    activeClasses: 'border-orange-400 bg-orange-50 ring-orange-400',
    badge: 'bg-orange-100 text-orange-700',
  },
  {
    id: 'azure',
    label: 'Microsoft Azure',
    shortName: 'Azure',
    description: 'App Service, AKS, Azure SQL',
    activeClasses: 'border-blue-500 bg-blue-50 ring-blue-500',
    badge: 'bg-blue-100 text-blue-700',
  },
  {
    id: 'gcp',
    label: 'Google Cloud',
    shortName: 'GCP',
    description: 'GKE, Cloud Run, BigQuery',
    activeClasses: 'border-green-500 bg-green-50 ring-green-500',
    badge: 'bg-green-100 text-green-700',
  },
];

export default function CSPSelector({ value, onChange }: CSPSelectorProps) {
  return (
    <fieldset>
      <legend className="text-sm font-medium text-gray-700 mb-3">Target Cloud Provider</legend>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        {CSP_OPTIONS.map((opt) => {
          const isSelected = value === opt.id;
          return (
            <label
              key={opt.id}
              htmlFor={`csp-${opt.id}`}
              className={`relative flex flex-col p-4 rounded-xl border-2 cursor-pointer transition-all select-none
                ${isSelected
                  ? `${opt.activeClasses} ring-2 ring-offset-1`
                  : 'border-gray-200 hover:border-gray-300 bg-white'}
              `}
            >
              <input
                type="radio"
                id={`csp-${opt.id}`}
                name="csp"
                value={opt.id}
                checked={isSelected}
                onChange={() => onChange(opt.id)}
                className="sr-only"
              />
              <span className={`self-start text-xs font-bold px-2 py-0.5 rounded-full mb-2 ${opt.badge}`}>
                {opt.shortName}
              </span>
              <span className="font-semibold text-gray-900 text-sm">{opt.label}</span>
              <span className="text-xs text-gray-500 mt-0.5">{opt.description}</span>
            </label>
          );
        })}
      </div>
    </fieldset>
  );
}
