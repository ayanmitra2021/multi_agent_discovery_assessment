import AssessmentForm from '@/components/AssessmentForm';

export default function Home() {
  return (
    <main className="min-h-screen bg-gray-50 flex flex-col">
      <div className="max-w-2xl w-full mx-auto px-4 py-16">
        <div className="text-center mb-10">
          <h1 className="text-3xl font-bold text-gray-900 tracking-tight">
            Cloud Migration Assessment
          </h1>
          <p className="mt-3 text-gray-500 text-sm leading-relaxed max-w-md mx-auto">
            Upload your application portfolio document and select a target cloud provider.
            The AI agent pipeline will produce a full migration assessment.
          </p>
        </div>

        <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-8">
          <AssessmentForm />
        </div>
      </div>
    </main>
  );
}
