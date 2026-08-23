"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { ArrowRight, BarChart3, DraftingCompass, Search } from "lucide-react";

type JobResponse = {
  job_id: string;
  status: "queued" | "running" | "completed" | "failed";
  progress: number;
  keyword: string;
  platform: string;
  locale: string;
  top_n: number;
  created_at: string;
  updated_at: string;
  error_message?: string | null;
  report?: {
    summary: {
      keyword: string;
      platform: string;
      locale: string;
      top_n: number;
    };
    metrics: {
      product_count: number;
      price_min: number;
      price_median: number;
      price_max: number;
      avg_rating: number;
      review_total: number;
      top_brand_share: number;
    };
    price_distribution: Array<{ bucket: string; count: number }>;
    top_competitors: Array<{
      rank: number;
      title: string;
      price: number;
      rating: number;
      review_count: number;
      brand: string;
    }>;
    voc: {
      pain_points: string[];
      selling_points: string[];
      visual_style: string[];
    };
    recommendation: {
      suggested_price: number;
      positioning: string;
      listing_focus: string[];
    };
  } | null;
};

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

const statusLabel = (status?: JobResponse["status"] | "idle") => {
  const labels = {
    queued: "排队中",
    running: "运行中",
    completed: "已完成",
    failed: "失败",
    idle: "空闲",
  };
  return labels[status ?? "idle"] ?? status;

};

const tiles = [
  {
    title: "Amazon 搜索分析",
    icon: Search,
    desc: "输入关键词，生成 Top 50 竞品报告。",
  },
  {
    title: "VOC 深度解析",
    icon: BarChart3,
    desc: "整理差评、Q&A 和文案，转成可执行洞察。",
  },
  {
    title: "Listing Draft",
    icon: DraftingCompass,
    desc: "把洞察变成可验证的 Amazon 草稿。",
  },
];

export default function HomePage() {
  const [keyword, setKeyword] = useState("desk lamp");
  const [job, setJob] = useState<JobResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const pollTimer = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      if (pollTimer.current) {
        window.clearInterval(pollTimer.current);
      }
    };
  }, []);

  const priceBars = useMemo(() => job?.report?.price_distribution ?? [], [job]);

  const stopPolling = () => {
    if (pollTimer.current) {
      window.clearInterval(pollTimer.current);
      pollTimer.current = null;
    }
  };

  const startPolling = (jobId: string) => {
    stopPolling();

    const poll = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/api/v1/jobs/${jobId}`);
        if (!response.ok) {
          throw new Error("job fetch failed");
        }
        const data = (await response.json()) as JobResponse;
        setJob(data);
        if (data.status === "completed" || data.status === "failed") {
          setLoading(false);
          stopPolling();
        }
      } catch {
        setLoading(false);
        stopPolling();
      }
    };

    void poll();
    pollTimer.current = window.setInterval(poll, 2000);
  };

  const handleAnalyze = async () => {
    if (!keyword.trim()) {
      return;
    }

    setLoading(true);
    setJob(null);
    stopPolling();

    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/jobs`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          keyword,
          platform: "amazon",
          locale: "US",
          top_n: 50,
        }),
      });

      if (!response.ok) {
        throw new Error("job create failed");
      }

      const data = (await response.json()) as JobResponse;
      startPolling(data.job_id);
    } catch {
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen bg-slate-50 text-slate-900">
      <section className="mx-auto flex max-w-6xl flex-col gap-10 px-6 py-10">
        <header className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-slate-500">Oversea</p>
            <h1 className="text-2xl font-semibold">Amazon 搜索分析</h1>
          </div>
          <div className="flex items-center gap-3">
            <Link
              href="/reports"
              className="inline-flex items-center gap-2 rounded-md border border-slate-200 bg-white px-4 py-2 text-sm font-medium"
            >
              打开报告 <ArrowRight size={16} />
            </Link>
            <Link
              href="/drafts"
              className="inline-flex items-center gap-2 rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white"
            >
              查看草稿 <ArrowRight size={16} />
            </Link>
          </div>
        </header>

        <section className="grid gap-4 border border-slate-200 bg-white p-5 md:grid-cols-[1fr_160px]">
          <label className="grid gap-2">
            <span className="text-xs uppercase tracking-wide text-slate-500">Amazon 关键词</span>
            <input
              value={keyword}
              onChange={(event) => setKeyword(event.target.value)}
              className="h-12 border border-slate-200 px-3 text-base outline-none"
            />
          </label>
          <button
            type="button"
            onClick={handleAnalyze}
            disabled={loading || keyword.trim().length === 0}
            className="inline-flex h-12 items-center justify-center gap-2 bg-slate-900 px-4 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-60"
          >
            <Search size={16} />
            {loading ? "分析中" : "开始分析"}
          </button>
        </section>

        <div className="grid gap-4 md:grid-cols-3">
          {tiles.map((tile) => (
            <article key={tile.title} className="rounded-lg border border-slate-200 bg-white p-5">
              <tile.icon className="mb-4 text-slate-700" size={18} />
              <h2 className="text-base font-semibold">{tile.title}</h2>
              <p className="mt-2 text-sm text-slate-600">{tile.desc}</p>
            </article>
          ))}
        </div>

        <section className="grid gap-4 md:grid-cols-[1.1fr_0.9fr]">
          <article className="rounded-lg border border-slate-200 bg-white p-5">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs uppercase tracking-wide text-slate-500">任务状态</p>
                <h2 className="mt-1 text-lg font-semibold">
                  {job ? `${job.keyword} / ${statusLabel(job.status)}` : "等待分析"}
                </h2>
              </div>
              <div className="text-right">
                <p className="text-xs uppercase tracking-wide text-slate-500">进度</p>
                <p className="mt-1 text-2xl font-semibold">{job ? `${job.progress}%` : loading ? "0%" : "—"}</p>
              </div>
            </div>

            <div className="mt-4 h-2 overflow-hidden bg-slate-100">
              <div
                className="h-full bg-red-600 transition-all"
                style={{ width: `${job?.progress ?? (loading ? 20 : 0)}%` }}
              />
            </div>

            <div className="mt-5 grid gap-3 md:grid-cols-4">
              {[
                { label: "Top N", value: job?.top_n ?? 50 },
                { label: "平台", value: job?.platform ?? "amazon" },
                { label: "地区", value: job?.locale ?? "US" },
                { label: "状态", value: statusLabel(job?.status ?? "idle") },
              ].map((item) => (
                <div key={item.label} className="border border-slate-200 p-3">
                  <p className="text-xs uppercase tracking-wide text-slate-500">{item.label}</p>
                  <p className="mt-2 text-sm font-semibold">{item.value}</p>
                </div>
              ))}
            </div>
          </article>

          <article className="rounded-lg border border-slate-200 bg-white p-5">
            <p className="text-xs uppercase tracking-wide text-slate-500">建议</p>
            <h2 className="mt-1 text-lg font-semibold">
              {job?.report ? job.report.recommendation.positioning : "等待报告"}
            </h2>
            <p className="mt-2 text-sm text-slate-600">
              建议价格：{job?.report ? `$${job.report.recommendation.suggested_price}` : "—"}
            </p>
            <div className="mt-4 grid gap-2">
              {(job?.report?.recommendation.listing_focus ?? []).map((item) => (
                <div key={item} className="border-l-2 border-red-600 pl-3 text-sm text-slate-700">
                  {item}
                </div>
              ))}
            </div>
          </article>
        </section>

        <section className="grid gap-4 md:grid-cols-[1.2fr_0.8fr]">
          <article className="rounded-lg border border-slate-200 bg-white p-5">
            <div className="flex items-center justify-between">
              <h2 className="text-base font-semibold">价格分布</h2>
              <span className="text-xs uppercase tracking-wide text-slate-500">Top 50</span>
            </div>
            <div className="mt-5 grid min-h-48 grid-cols-8 items-end gap-3 border-b border-l border-slate-200 px-4 pb-4 pt-3">
              {priceBars.map((bar) => {
                const max = 41;
                return (
                  <div key={bar.bucket} className="flex h-full flex-col justify-end gap-2">
                    <div className="flex items-end justify-center">
                      <div
                        className="w-full bg-slate-900"
                        style={{ height: `${Math.max((bar.count / max) * 100, 8)}%` }}
                      />
                    </div>
                    <div className="text-center text-[11px] text-slate-500">{bar.bucket}</div>
                  </div>
                );
              })}
            </div>
          </article>

          <article className="rounded-lg border border-slate-200 bg-white p-5">
            <h2 className="text-base font-semibold">VOC 痛点</h2>
            <div className="mt-4 grid gap-3">
              {(job?.report?.voc.pain_points ?? []).map((item) => (
                <div key={item} className="border border-slate-200 px-3 py-2 text-sm text-slate-700">
                  {item}
                </div>
              ))}
            </div>
          </article>
        </section>

        <section className="grid gap-4 md:grid-cols-[1fr_1fr]">
          <article className="rounded-lg border border-slate-200 bg-white p-5">
            <h2 className="text-base font-semibold">Top 竞品</h2>
            <div className="mt-4 divide-y divide-slate-200">
              {(job?.report?.top_competitors ?? []).map((item) => (
                <div key={item.rank} className="grid grid-cols-[48px_1fr_110px] gap-3 py-3">
                  <div className="text-lg font-semibold text-slate-500">#{item.rank}</div>
                  <div>
                    <p className="text-sm font-medium">{item.title}</p>
                    <p className="text-xs text-slate-500">{item.brand}</p>
                  </div>
                  <div className="text-right text-sm text-slate-700">
                    <div>${item.price.toFixed(2)}</div>
                    <div>
                      {item.rating.toFixed(1)} / {item.review_count}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </article>

          <article className="rounded-lg border border-slate-200 bg-white p-5">
            <h2 className="text-base font-semibold">卖点</h2>
            <div className="mt-4 grid gap-3">
              {(job?.report?.voc.selling_points ?? []).map((item) => (
                <div key={item} className="border-l-2 border-slate-900 pl-3 text-sm text-slate-700">
                  {item}
                </div>
              ))}
            </div>
            <h3 className="mt-6 text-sm font-semibold uppercase tracking-wide text-slate-500">
              视觉风格
            </h3>
            <div className="mt-3 flex flex-wrap gap-2">
              {(job?.report?.voc.visual_style ?? []).map((item) => (
                <span key={item} className="border border-slate-200 px-3 py-1 text-xs text-slate-700">
                  {item}
                </span>
              ))}
            </div>
          </article>
        </section>
      </section>
    </main>
  );
}
