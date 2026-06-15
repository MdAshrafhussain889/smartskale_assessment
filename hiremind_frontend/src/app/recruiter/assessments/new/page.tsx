"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { useAuthStore } from "@/store/auth";

const QUESTION_TYPES = ["mcq", "coding", "sql", "aptitude"];

type TemplateConfig = {
  role: string;
  skills: string;
  counts: Record<string, number>;
  duration: number;
  passScore: number;
  types: string[];
  jobDescription: string;
};

const TEMPLATES: Record<string, TemplateConfig> = {
  "Backend Engineer": {
    role: "Backend Engineer",
    skills: "Python, FastAPI, PostgreSQL, Docker, REST APIs",
    counts: { mcq: 8, coding: 4, sql: 5, aptitude: 3 },
    duration: 90,
    passScore: 70,
    types: ["mcq", "coding", "sql"],
    jobDescription:
      "Backend Engineer: building APIs, database design, and scalable services. Experience with Python, FastAPI, and PostgreSQL.",
  },
  "Frontend Engineer": {
    role: "Frontend Engineer",
    skills: "JavaScript, TypeScript, React, CSS, Testing",
    counts: { mcq: 8, coding: 4, sql: 0, aptitude: 2 },
    duration: 75,
    passScore: 65,
    types: ["mcq", "coding"],
    jobDescription: "Frontend Engineer: React, TypeScript, component design, and testing.",
  },
  "Full Stack Developer": {
    role: "Full Stack Developer",
    skills: "JavaScript, TypeScript, Python, React, SQL, REST APIs",
    counts: { mcq: 8, coding: 5, sql: 3, aptitude: 2 },
    duration: 120,
    passScore: 70,
    types: ["mcq", "coding", "sql"],
    jobDescription: "Full Stack Developer: frontend and backend skills across the stack.",
  },
  "Data Analyst": {
    role: "Data Analyst",
    skills: "SQL, Excel, Python, Data Visualization",
    counts: { mcq: 6, coding: 0, sql: 8, aptitude: 4 },
    duration: 80,
    passScore: 65,
    types: ["mcq", "sql"],
    jobDescription: "Data Analyst: SQL, data cleaning, and visualization.",
  },
  "Data Scientist": {
    role: "Data Scientist",
    skills: "Python, Statistics, Machine Learning, SQL, Pandas",
    counts: { mcq: 6, coding: 4, sql: 4, aptitude: 4 },
    duration: 120,
    passScore: 70,
    types: ["mcq", "coding", "sql"],
    jobDescription: "Data Scientist: ML modeling, experiments, and data pipelines.",
  },
  "DevOps Engineer": {
    role: "DevOps Engineer",
    skills: "Docker, Kubernetes, CI/CD, Linux, Networking",
    counts: { mcq: 6, coding: 3, sql: 0, aptitude: 4 },
    duration: 90,
    passScore: 68,
    types: ["mcq", "coding"],
    jobDescription: "DevOps Engineer: CI/CD, infra as code, and system reliability.",
  },
  "GenAI Engineer": {
    role: "GenAI Engineer",
    skills: "Python, ML, Prompt Engineering, LLMs, APIs",
    counts: { mcq: 5, coding: 0, sql: 2, aptitude: 5 },
    duration: 100,
    passScore: 72,
    types: ["mcq", "sql", "aptitude"],
    jobDescription: "GenAI Engineer: working with LLMs, prompt design, and evaluation.",
  },
};

export default function NewAssessmentPage() {
  const router = useRouter();
  const token = useAuthStore((s) => s.accessToken)!;
  const [title, setTitle] = useState("");
  const [template, setTemplate] = useState("Custom Assessment");
  const [role, setRole] = useState("Backend Engineer");
  const [skills, setSkills] = useState("Python, SQL, REST APIs");
  const [jobDescription, setJobDescription] = useState(
    "Looking for a Backend Engineer with Python, SQL, and REST API skills.",
  );
  const [experienceLevel, setExperienceLevel] = useState("1-3 Years");
  const [types, setTypes] = useState<string[]>(["mcq", "coding"]);
  const [duration, setDuration] = useState(60);
  const [passScore, setPassScore] = useState(70);
  const [proctoring, setProctoring] = useState(true);
  const [generateAi, setGenerateAi] = useState(true);
  const [questionCounts, setQuestionCounts] = useState<Record<string, number>>({
    mcq: 10,
    coding: 2,
    sql: 5,
    aptitude: 10,
  });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const selectedQuestionCount = types.reduce(
    (total, type) => total + (Number(questionCounts[type]) || 0),
    0,
  );

  function toggleType(type: string) {
    setTypes((prev) =>
      prev.includes(type) ? prev.filter((t) => t !== type) : [...prev, type],
    );
  }

  function applyTemplate(name: string) {
    const next = TEMPLATES[name];
    if (!next) return;

    setRole(next.role);
    setSkills(next.skills);
    setQuestionCounts(next.counts);
    setDuration(next.duration);
    setPassScore(next.passScore);
    setTypes(next.types);
    setJobDescription(next.jobDescription);
    if (!title.trim()) {
      setTitle(`${next.role} Hiring`);
    }
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (types.length === 0) {
      setError("Select at least one question type");
      return;
    }
    if (generateAi && selectedQuestionCount <= 0) {
      setError("Set at least one question");
      return;
    }

    setError("");
    setLoading(true);
    try {
      const assessment = await api.createAssessment(token, {
        title,
        role,
        types,
        duration_minutes: duration,
        proctoring,
        adaptive: false,
        pass_score: passScore,
        proctoring_options: {
          webcamMonitoring: proctoring,
          tabSwitchDetection: proctoring,
          fullscreenEnforce: proctoring,
          multipleFaceDetection: false,
          blockCopyPaste: proctoring,
          blockRightClick: proctoring,
          aiChatDetection: proctoring,
        },
      });

      if (generateAi) {
        const countsFiltered = Object.fromEntries(
          Object.entries(questionCounts).filter(([key]) => types.includes(key)),
        );
        await api.generateQuestions(
          token,
          {
            role,
            skills: skills.split(",").map((s) => s.trim()).filter(Boolean),
            difficulty: "medium",
            types,
            counts: countsFiltered,
            job_description: jobDescription,
            experience_level: experienceLevel,
          },
          assessment.id,
        );
      }

      router.push(`/recruiter/assessments/${assessment.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create assessment");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto max-w-4xl px-4 sm:px-6">
      <Link href="/recruiter" className="text-sm text-muted hover:text-accent">
        Back to dashboard
      </Link>

      <div className="mt-4 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-sans text-3xl font-extrabold">Create Assessment</h1>
          <p className="mt-1 text-sm text-muted">Choose a role, sections, and question count.</p>
        </div>
        <select
          className="input-field max-w-xs"
          value={template}
          onChange={(e) => {
            const value = e.target.value;
            setTemplate(value);
            if (value !== "Custom Assessment") applyTemplate(value);
          }}
        >
          <option>Custom Assessment</option>
          {Object.keys(TEMPLATES).map((name) => (
            <option key={name}>{name}</option>
          ))}
        </select>
      </div>

      <form onSubmit={handleSubmit} className="card-panel mt-6 space-y-6">
        <div className="grid gap-4 md:grid-cols-2">
          <div>
            <label className="mb-1 block text-xs text-muted">Assessment Name</label>
            <input
              className="input-field"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Backend Engineer Hiring"
              required
            />
          </div>
          <div>
            <label className="mb-1 block text-xs text-muted">Target Role</label>
            <input className="input-field" value={role} onChange={(e) => setRole(e.target.value)} required />
          </div>
          <div>
            <label className="mb-1 block text-xs text-muted">Skills</label>
            <input className="input-field" value={skills} onChange={(e) => setSkills(e.target.value)} />
          </div>
          <div>
            <label className="mb-1 block text-xs text-muted">Experience Level</label>
            <select
              className="input-field"
              value={experienceLevel}
              onChange={(e) => setExperienceLevel(e.target.value)}
            >
              <option>Fresher</option>
              <option>0-1 Years</option>
              <option>1-3 Years</option>
              <option>3-5 Years</option>
              <option>5+ Years</option>
            </select>
          </div>
          <div>
            <label className="mb-1 block text-xs text-muted">Duration</label>
            <input
              className="input-field"
              type="number"
              min={15}
              value={duration}
              onChange={(e) => setDuration(Number(e.target.value))}
            />
          </div>
          <div>
            <label className="mb-1 block text-xs text-muted">Pass Score</label>
            <input
              className="input-field"
              type="number"
              min={0}
              max={100}
              value={passScore}
              onChange={(e) => setPassScore(Number(e.target.value))}
            />
          </div>
        </div>

        <div className="rounded-lg border border-border bg-surface p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-sm font-semibold">Question Sections</p>
              <p className="text-xs text-muted">{selectedQuestionCount} questions selected</p>
            </div>
            <label className="flex items-center gap-2 text-sm text-muted">
              <input type="checkbox" checked={generateAi} onChange={(e) => setGenerateAi(e.target.checked)} />
              Generate with AI
            </label>
          </div>

          <div className="mt-4 flex flex-wrap gap-2">
            {QUESTION_TYPES.map((type) => (
              <button
                key={type}
                type="button"
                onClick={() => toggleType(type)}
                className={`rounded border px-3 py-1.5 text-xs uppercase ${
                  types.includes(type)
                    ? "border-accent bg-accent/10 text-accent"
                    : "border-border text-muted"
                }`}
              >
                {type}
              </button>
            ))}
          </div>

          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            {types.map((type) => (
              <div key={type}>
                <label className="mb-1 block text-xs uppercase text-muted">{type}</label>
                <input
                  className="input-field"
                  type="number"
                  min={0}
                  max={50}
                  value={questionCounts[type] ?? 0}
                  onChange={(e) =>
                    setQuestionCounts((prev) => ({ ...prev, [type]: Number(e.target.value) }))
                  }
                  disabled={!generateAi}
                />
              </div>
            ))}
          </div>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border pt-5">
          <label className="flex items-center gap-2 text-sm text-muted">
            <input type="checkbox" checked={proctoring} onChange={(e) => setProctoring(e.target.checked)} />
            Enable proctoring
          </label>
          <div className="flex flex-wrap items-center justify-end gap-3">
            {error && <p className="text-sm text-red">{error}</p>}
            <button type="submit" className="btn-primary" disabled={loading}>
              {loading ? "Creating..." : "Create Assessment"}
            </button>
          </div>
        </div>
      </form>
    </div>
  );
}
