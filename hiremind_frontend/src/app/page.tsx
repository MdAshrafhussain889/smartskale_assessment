import Link from "next/link";
import { Navbar } from "@/components/Navbar";

export default function HomePage() {
  return (
    <main>
      <Navbar />
      <section className="mx-auto flex max-w-4xl flex-col items-center px-4 py-24 text-center">
        <p className="mb-4 rounded-full border border-accent/30 bg-accent/5 px-4 py-1 text-[11px] uppercase tracking-[0.3em] text-accent">
          Enterprise AI Architecture
        </p>
        <h1 className="font-sans text-5xl font-extrabold tracking-tight md:text-7xl">
          SmartSkale <span className="text-accent">HireMind AI</span>
        </h1>
        <p className="mt-6 max-w-2xl text-base text-muted md:text-lg">
          Intelligent adaptive hiring and assessment — AI question generation,
          sandboxed code execution, live proctoring, and GPT-4o evaluation.
        </p>
        <div className="mt-10 flex flex-wrap justify-center gap-3">
          <Link href="/register" className="btn-primary">
            Get Started
          </Link>
          <Link href="/login" className="btn-secondary">
            Sign In
          </Link>
        </div>
        <div className="mt-16 grid w-full gap-4 text-left md:grid-cols-3">
          {[
            { title: "For Recruiters", desc: "Create assessments, generate questions with AI, evaluate candidates." },
            { title: "For Candidates", desc: "Take MCQ and coding tests in a secure proctored session." },
            { title: "AI Reports", desc: "Composite scores, strengths, gaps, and hiring recommendations." },
          ].map((item) => (
            <div key={item.title} className="card-panel">
              <h3 className="font-sans text-sm font-bold text-accent">{item.title}</h3>
              <p className="mt-2 text-sm text-muted">{item.desc}</p>
            </div>
          ))}
        </div>
      </section>
    </main>
  );
}
