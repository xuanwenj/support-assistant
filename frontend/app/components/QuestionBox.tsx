// components/QuestionBox.tsx
"use client";
import { useState } from "react";

export default function QuestionBox() {
  const [question, setQuestion] = useState("");

  return (
    <div>
      <input
        value={question}
        onChange={(e) => setQuestion(e.target.value)}
        placeholder="Ask a question..."
      />
      <p>You typed: {question}</p>
    </div>
  );
}
