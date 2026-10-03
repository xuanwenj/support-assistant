import QuestionBox from "@/app/components/QuestionBox";

export default function HomePage() {
  return (
    <main className="mx-auto w-full max-w-3xl p-8">
      <h1 className="text-2xl font-semibold">Ask a question</h1>
      <QuestionBox />
    </main>
  );
}
