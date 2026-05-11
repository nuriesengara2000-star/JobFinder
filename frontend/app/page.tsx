'use client';

import { FormEvent, useMemo, useState } from 'react';
import { API_URL, streamJobSearch } from '../lib/api';

type Job = {
  title?: string;
  company?: string;
  salary?: string;
  requirements?: string;
  url?: string;
  source?: string;
  match_score?: number;
  match_reason?: string;
  level_warning?: string;
};

const sampleResume = `Frontend Developer\nSkills: React, JavaScript, TypeScript, HTML, CSS, Redux, REST API, Git\nExperience: 1 year of pet projects and internship experience\nLocation: Kazakhstan / Remote\nGoal: Junior Frontend Developer or React Developer role`;

export default function Home() {
  const [resumeText, setResumeText] = useState(sampleResume);
  const [status, setStatus] = useState('Ready to analyze your resume.');
  const [answer, setAnswer] = useState('');
  const [jobs, setJobs] = useState<Job[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  const stats = useMemo(
    () => [
      { label: 'Sources', value: '4+' },
      { label: 'Fit analysis', value: 'AI' },
      { label: 'Mode', value: 'Streaming' },
    ],
    [],
  );

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError('');
    setAnswer('');
    setJobs([]);
    setIsLoading(true);
    setStatus('Starting agent...');

    try {
      await streamJobSearch(resumeText, ({ event, data }) => {
        if (event === 'status') {
          setStatus(String(data.message || 'Agent is working...'));
        }

        if (event === 'error') {
          setError(String(data.message || 'Something went wrong.'));
          setStatus('Agent stopped.');
        }

        if (event === 'final') {
          setAnswer(String(data.answer || ''));
          setJobs(Array.isArray(data.jobs) ? (data.jobs as Job[]) : []);
          setStatus(`Done. Found ${String(data.jobs_count || 0)} ranked vacancies from ${String(data.raw_jobs_count || 0)} collected jobs.`);
        }
      });
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : 'Unknown error.');
      setStatus('Request failed.');
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <main className="min-h-screen overflow-hidden bg-[#07111f] text-white">
      <section className="relative isolate px-6 py-8 sm:px-10 lg:px-16">
        <div className="absolute inset-0 -z-10 bg-[radial-gradient(circle_at_top_left,_rgba(45,212,191,0.22),_transparent_32%),radial-gradient(circle_at_top_right,_rgba(96,165,250,0.2),_transparent_30%),linear-gradient(135deg,#07111f_0%,#0f172a_45%,#111827_100%)]" />
        <div className="absolute left-1/2 top-10 -z-10 h-72 w-72 -translate-x-1/2 rounded-full bg-cyan-400/10 blur-3xl" />

        <nav className="mx-auto flex max-w-7xl items-center justify-between rounded-3xl border border-white/10 bg-white/5 px-5 py-4 backdrop-blur-xl">
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-cyan-300 text-xl font-black text-slate-950 shadow-lg shadow-cyan-500/20">
              JF
            </div>
            <div>
              <p className="text-sm font-semibold tracking-wide text-white">JobFinder AI</p>
              <p className="text-xs text-slate-400">Autonomous job-search agent</p>
            </div>
          </div>
          <a
            href={`${API_URL}/docs`}
            target="_blank"
            className="rounded-full border border-white/15 px-4 py-2 text-sm font-medium text-slate-200 transition hover:border-cyan-300/60 hover:text-cyan-200"
          >
            API Docs
          </a>
        </nav>

        <div className="mx-auto grid max-w-7xl gap-8 py-12 lg:grid-cols-[0.95fr_1.05fr] lg:items-center">
          <div>
            <div className="mb-5 inline-flex rounded-full border border-cyan-300/20 bg-cyan-300/10 px-4 py-2 text-sm text-cyan-100">
              Resume → AI search → ranked vacancies
            </div>
            <h1 className="max-w-3xl text-5xl font-black leading-tight tracking-tight sm:text-6xl">
              Find better jobs with an AI agent that understands your resume.
            </h1>
            <p className="mt-6 max-w-2xl text-lg leading-8 text-slate-300">
              JobFinder searches multiple vacancy sources, compares your skills with real job requirements,
              and returns practical opportunities instead of random links.
            </p>

            <div className="mt-8 grid max-w-xl grid-cols-3 gap-3">
              {stats.map((item) => (
                <div key={item.label} className="rounded-3xl border border-white/10 bg-white/7 p-4 backdrop-blur">
                  <p className="text-2xl font-black text-white">{item.value}</p>
                  <p className="mt-1 text-xs uppercase tracking-[0.2em] text-slate-400">{item.label}</p>
                </div>
              ))}
            </div>
          </div>

          <form onSubmit={handleSubmit} className="rounded-[2rem] border border-white/10 bg-white/10 p-4 shadow-2xl shadow-black/30 backdrop-blur-2xl sm:p-6">
            <div className="mb-4 flex items-center justify-between gap-4">
              <div>
                <h2 className="text-xl font-bold">Paste your resume</h2>
                <p className="text-sm text-slate-400">Minimum 30 characters. English or Russian works.</p>
              </div>
              <span className="rounded-full bg-emerald-300/10 px-3 py-1 text-xs font-semibold text-emerald-200">
                Live API
              </span>
            </div>

            <textarea
              value={resumeText}
              onChange={(event) => setResumeText(event.target.value)}
              className="h-72 w-full resize-none rounded-3xl border border-white/10 bg-slate-950/70 p-5 text-sm leading-6 text-slate-100 outline-none transition placeholder:text-slate-500 focus:border-cyan-300/60 focus:ring-4 focus:ring-cyan-300/10"
              placeholder="Paste resume text here..."
            />

            <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <p className="text-sm text-slate-400">{status}</p>
              <button
                disabled={isLoading}
                className="rounded-2xl bg-cyan-300 px-6 py-3 font-bold text-slate-950 shadow-lg shadow-cyan-500/20 transition hover:-translate-y-0.5 hover:bg-cyan-200 disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:translate-y-0"
              >
                {isLoading ? 'Agent is searching...' : 'Find matching jobs'}
              </button>
            </div>
          </form>
        </div>
      </section>

      <section className="px-6 pb-14 sm:px-10 lg:px-16">
        <div className="mx-auto grid max-w-7xl gap-6 lg:grid-cols-[0.85fr_1.15fr]">
          <aside className="rounded-[2rem] border border-white/10 bg-white/[0.06] p-6 backdrop-blur-xl">
            <h3 className="text-lg font-bold">Agent workflow</h3>
            <div className="mt-5 space-y-4">
              {['Parse resume skills and target role', 'Search real vacancies from job platforms', 'Rank opportunities by relevance', 'Return links, salary and short notes'].map((step, index) => (
                <div key={step} className="flex gap-4 rounded-2xl border border-white/10 bg-slate-950/40 p-4">
                  <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-white/10 text-sm font-bold text-cyan-200">
                    {index + 1}
                  </span>
                  <p className="text-sm leading-6 text-slate-300">{step}</p>
                </div>
              ))}
            </div>
          </aside>

          <div className="rounded-[2rem] border border-white/10 bg-white/[0.06] p-6 backdrop-blur-xl">
            <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
              <div>
                <h3 className="text-lg font-bold">Search result</h3>
                <p className="text-sm text-slate-400">The agent response appears here after streaming finishes.</p>
              </div>
              {jobs.length > 0 && (
                <span className="rounded-full bg-white/10 px-3 py-1 text-xs font-semibold text-slate-300">
                  {jobs.length} vacancies collected
                </span>
              )}
            </div>

            {error && <div className="mt-5 rounded-2xl border border-red-300/20 bg-red-400/10 p-4 text-sm text-red-100">{error}</div>}

            {!answer && !error && (
              <div className="mt-5 rounded-3xl border border-dashed border-white/15 bg-slate-950/30 p-8 text-center text-slate-400">
                Paste your resume and start the agent to see matched jobs.
              </div>
            )}

            {answer && (
              <pre className="mt-5 max-h-[520px] whitespace-pre-wrap rounded-3xl border border-white/10 bg-slate-950/70 p-5 text-sm leading-7 text-slate-100 overflow-auto">
                {answer}
              </pre>
            )}

            {jobs.length > 0 && (
              <div className="mt-6 grid gap-4 md:grid-cols-2">
                {jobs.slice(0, 6).map((job, index) => (
                  <a
                    key={`${job.url || job.title}-${index}`}
                    href={job.url || '#'}
                    target="_blank"
                    className="group rounded-3xl border border-white/10 bg-slate-950/45 p-5 transition hover:-translate-y-1 hover:border-cyan-300/40 hover:bg-slate-900/80"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <h4 className="font-bold text-white group-hover:text-cyan-100">{job.title || 'Untitled role'}</h4>
                      <span className="rounded-full bg-cyan-300/10 px-2 py-1 text-[11px] font-semibold text-cyan-200">
                        {job.source || 'source'}
                      </span>
                    </div>
                    <p className="mt-2 text-sm text-slate-300">{job.company || 'Company not specified'}</p>
                    <div className="mt-3 flex flex-wrap items-center gap-2">
                      {typeof job.match_score === 'number' && (
                        <span className="rounded-full bg-emerald-300/10 px-3 py-1 text-xs font-bold text-emerald-200">
                          {job.match_score}/100 match
                        </span>
                      )}
                      {job.salary && <span className="rounded-full bg-white/10 px-3 py-1 text-xs font-semibold text-emerald-100">{job.salary}</span>}
                    </div>
                    {job.match_reason && <p className="mt-3 text-sm leading-6 text-cyan-100">{job.match_reason}</p>}
                    {job.level_warning && <p className="mt-3 rounded-2xl border border-amber-300/20 bg-amber-300/10 p-3 text-xs leading-5 text-amber-100">{job.level_warning}</p>}
                    <p className="mt-3 line-clamp-3 text-sm leading-6 text-slate-400">{job.requirements || 'Open vacancy link for details.'}</p>
                  </a>
                ))}
              </div>
            )}
          </div>
        </div>
      </section>
    </main>
  );
}
