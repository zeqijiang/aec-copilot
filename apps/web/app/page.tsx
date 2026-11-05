"use client";

import { useMemo, useState } from "react";
import ModelViewer, { type ElementRecord } from "@/components/ModelViewer";

const API = process.env.NEXT_PUBLIC_AEC_API || "http://127.0.0.1:8000";
const examples = [
  "生成一栋30m×20m的两层小楼，层高3.6m，外墙200mm，中间加一道隔墙，四个角放柱子",
  "生成一个6m×4m的房间，层高3.6m，墙厚200mm，包含楼板",
  "在0,0画一面6m长的墙",
];

type Attempt = { attempt: number; status: string; elapsed_ms: number; verification: { passed: boolean; differences: any[]; screenshot?: string } };
type RunResult = {
  run_id: string; status: string; backend: string; engine: string; instruction: string;
  elements: ElementRecord[]; attempts: Attempt[]; plan: any; reports: Record<string, string>; output_dir: string;
};
type Preview = { plan: any; calls: any[] };

export default function Home() {
  const [instruction, setInstruction] = useState(examples[0]);
  const [engine, setEngine] = useState("revit");
  const [busy, setBusy] = useState<"preview" | "run" | null>(null);
  const [result, setResult] = useState<RunResult | null>(null);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [error, setError] = useState("");
  const [tab, setTab] = useState<"model" | "plan" | "trace">("model");
  const [audit, setAudit] = useState<any>(null);

  const counts = useMemo(() => (result?.elements || []).reduce<Record<string, number>>((acc, item) => {
    acc[item.type] = (acc[item.type] || 0) + 1; return acc;
  }, {}), [result]);

  async function request(path: string, body: any) {
    const response = await fetch(`${API}${path}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    const data = await response.json();
    if (!response.ok && !data.run_id) throw new Error(data?.error?.message || data?.message || `请求失败 (${response.status})`);
    return data;
  }

  async function doPreview() {
    setBusy("preview"); setError(""); setAudit(null);
    try { setPreview(await request("/api/plan", { instruction, engine })); setTab("plan"); }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(null); }
  }

  async function doRun() {
    setBusy("run"); setError(""); setAudit(null);
    try {
      const data = await request("/api/run", { instruction, engine, max_attempts: 3, write_reports: true });
      setResult(data); setPreview({ plan: data.plan, calls: [] }); setTab("model");
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(null); }
  }

  async function doAudit() {
    if (!result) return;
    setError("");
    try { setAudit(await request("/api/audit", { elements: result.elements, write_reports: false })); setTab("trace"); }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); }
  }

  function artifact(filename: string) {
    return result ? `${API}/artifacts/${result.run_id}/${filename}` : "#";
  }

  return (
    <main>
      <header className="topbar">
        <a className="brand" href="/" aria-label="蓝图智匠首页"><span className="brand-mark">蓝</span><span><strong>蓝图智匠</strong><small>AEC COPILOT</small></span></a>
        <div className="topbar-meta"><span className="status-dot" />本地工作台 <span className="version">v0.1.0</span></div>
      </header>
      <section className="hero">
        <div><p className="eyebrow">NATURAL LANGUAGE → VERIFIABLE MODEL</p><h1>让每一句需求，<br /><em>都有据可查地成为模型。</em></h1></div>
        <p className="hero-copy">从中文意图到结构化 DSL，从事务执行到视觉预览与逐项校验。<br />每一步可预览、可重放、可回滚。</p>
      </section>
      <div className="workspace">
        <section className="command-panel panel">
          <div className="panel-heading"><span>01 / 描述需求</span><span className="engine-label">目标引擎</span></div>
          <div className="engine-switch" role="group" aria-label="目标引擎">
            {[ ["revit", "Revit BIM"], ["acad", "AutoCAD 2D"], ["sw", "SolidWorks"] ].map(([value, label]) => <button key={value} className={engine === value ? "active" : ""} onClick={() => setEngine(value)}>{label}</button>)}
          </div>
          <textarea value={instruction} onChange={(event) => setInstruction(event.target.value)} aria-label="中文建模需求" rows={5} />
          <div className="examples"><span>试试：</span>{examples.map((example, index) => <button key={example} onClick={() => { setInstruction(example); setEngine("revit"); }}>{["两层小楼", "矩形房间", "单面墙"][index]}</button>)}</div>
          <div className="actions"><button className="secondary" onClick={doPreview} disabled={!!busy || !instruction.trim()}>{busy === "preview" ? "正在编译…" : "预览计划"}</button><button className="primary" onClick={doRun} disabled={!!busy || !instruction.trim()}>{busy === "run" ? "正在执行与校验…" : "生成模型 →"}</button></div>
          <p className="safety-note">当前为 <strong>SIMULATION</strong> 模式，不写入本机 CAD/BIM 工程。</p>
          {error && <div className="error" role="alert">{error}<small>请先启动 Python API：aec serve</small></div>}
        </section>
        <section className="viewer-panel panel">
          <div className="panel-heading"><span>02 / 模型与验证</span>{result && <span className={`result-badge ${result.status}`}>{result.status === "passed" ? "✓ 校验通过" : "未通过"}</span>}</div>
          <div className="tabs"><button className={tab === "model" ? "active" : ""} onClick={() => setTab("model")}>三维预览</button><button className={tab === "plan" ? "active" : ""} onClick={() => setTab("plan")}>建模 DSL</button><button className={tab === "trace" ? "active" : ""} onClick={() => setTab("trace")}>执行轨迹</button></div>
          <div className="tab-content">
            {tab === "model" && (result ? <ModelViewer elements={result.elements} /> : <div className="empty"><div className="empty-grid" /><strong>模型将在这里生成</strong><p>可拖拽旋转、滚轮缩放</p></div>)}
            {tab === "plan" && <pre className="code-view">{preview ? JSON.stringify(preview.plan, null, 2) : "// 点击“预览计划”查看结构化建模 DSL"}</pre>}
            {tab === "trace" && <div className="trace-view">{result?.attempts.map((attempt) => <div className="trace-item" key={attempt.attempt}><span className={attempt.verification.passed ? "trace-ok" : "trace-fail"}>{attempt.attempt}</span><div><strong>{attempt.verification.passed ? "模型清单校验通过" : "发现差异，已回滚"}</strong><p>{attempt.elapsed_ms.toFixed(1)} ms · {attempt.verification.differences.length} 个差异</p>{attempt.verification.differences.slice(0, 3).map((difference, i) => <small key={i}>{difference.message}</small>)}</div></div>)}{!result && <div className="empty small"><strong>尚无执行记录</strong></div>}{audit && <div className="audit-box"><strong>项目规则审图：{audit.issue_count} 项</strong>{audit.issues.map((issue: any, i: number) => <p key={i}>[{issue.severity}] {issue.rule_id} · {issue.message}</p>)}<small>{audit.disclaimer}</small></div>}</div>}
          </div>
          {result && <div className="viewer-footer"><span>{result.engine.toUpperCase()} · {result.elements.length} 个构件 · {result.attempts.length} 轮</span><button onClick={doAudit}>运行项目规则审图</button></div>}
        </section>
      </div>
      {result && <section className="summary-grid">
        <div className="panel summary"><div className="panel-heading"><span>03 / 构件清单</span></div><div className="counts">{Object.entries(counts).map(([type, count]) => <div key={type}><strong>{count}</strong><span>{type}</span></div>)}</div></div>
        <div className="panel deliverables"><div className="panel-heading"><span>04 / 交付物</span></div><a href={artifact("model-schedule.xlsx")}>Excel 构件明细 <span>下载 ↗</span></a><a href={artifact("modeling-report.pdf")}>PDF 建模报告 <span>下载 ↗</span></a><a href={artifact("run.json")}>JSON 完整执行记录 <span>下载 ↗</span></a></div>
      </section>}
      <footer><span>AEC Copilot / 蓝图智匠</span><span>模拟验证 ≠ Revit / AutoCAD / SolidWorks 实机验收</span></footer>
    </main>
  );
}
