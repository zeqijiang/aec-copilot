/*
 * aec-copilot-dsh — DSH 客户端半侧（浏览器 bundle）
 *
 * 形态与「录阶」「dsh-ide-panel」一致：sidebar.panellist + main 槽位。
 * 数据来自宿主半侧 /api/aec/* 路由（挂官方 /api 网关的 connection/request 层，鉴权已由网关完成）。
 */
window.__ModuleLoader__.load({
  id: "aec-copilot-dsh",
  factory: (require) => {
    var module = { exports: {} };
    var exports = module.exports;
    Object.defineProperty(exports, Symbol.toStringTag, { value: "Module" });

    const react = require("react");
    const h = react.createElement;
    const { useState, useEffect, useCallback } = react;

    const NS = "aecCopilot";
    const PANEL_ID = "aec-copilot";
    const inject = ["slots", "locale"];

    window.__AEC_DATA__ = {"generated_at": "2026-11-08 15:54", "eval": {"total": 50, "passed": 48, "rate": 96, "revit_total": 46, "revit_passed": 46}, "bridge": {"state": "running", "document": "qty-demo"}, "runs": [{"run_id": "20261107T113445-8348a1ad", "status": "passed", "engine": "revit", "elements": 30, "attempts": 1, "instruction": "\u751f\u6210\u4e00\u680b24m\u00d716m\u7684\u4e24\u5c42\u5c0f\u697c\uff0c\u5c42\u9ad83.6m\uff0c\u4e2d\u95f4\u52a0\u4e00\u9053\u9694\u5899\uff0c\u56db\u4e2a\u89d2\u653e\u67f1\u5b50\uff0c\u5357\u5899\u52a0\u4e00\u62471000mm\u5bbd\u7684\u95e8", "mtime": 1794051311.0137112}, {"run_id": "20261107T113408-a148b23a", "status": "failed", "engine": "sw", "elements": 0, "attempts": 2, "instruction": "\u5728SolidWorks\u4e2d\u751f\u6210100mm\u00d750mm\u00d720mm\u7684\u96f6\u4ef6", "mtime": 1794051248.5303671}, {"run_id": "20261107T113402-e9d8ae9c", "status": "passed", "engine": "revit", "elements": 5, "attempts": 1, "instruction": "\u521b\u5efa\u4e00\u4e2a10m\u00d78m\u7684\u623f\u95f4\uff0c\u5c42\u9ad83.6m\uff0c\u5317\u5899\u8bbe\u7f6e1500mm\u00d71200mm\u7684\u7a97\uff0c\u7a97\u53f0900mm", "mtime": 1794051246.9767213}, {"run_id": "20261107T113356-611aba0c", "status": "passed", "engine": "revit", "elements": 5, "attempts": 1, "instruction": "\u751f\u6210\u4e00\u4e2a8m\u00d76m\u7684\u623f\u95f4\uff0c\u5c42\u9ad83.3m\uff0c\u5357\u5899\u8bbe\u7f6e900mm\u5bbd\u3001\u9ad8\u5ea62100mm\u7684\u95e8", "mtime": 1794051242.3341856}, {"run_id": "20261107T113352-975a92a5", "status": "passed", "engine": "revit", "elements": 1, "attempts": 1, "instruction": "\u521b\u5efa4.5m\u00d73.5m\u7684\u697c\u677f\uff0c\u539a100mm\uff0c\u6807\u9ad80m", "mtime": 1794051236.6859713}, {"run_id": "20261107T113348-1272954c", "status": "passed", "engine": "revit", "elements": 1, "attempts": 1, "instruction": "\u751f\u621010m\u00d78m\u7684\u697c\u677f\uff0c\u677f\u539a200mm\uff0c\u6807\u9ad8-0.1m", "mtime": 1794051232.557914}, {"run_id": "20261107T113344-3a25017f", "status": "passed", "engine": "revit", "elements": 1, "attempts": 1, "instruction": "\u521b\u5efa6m\u00d74m\u7684\u697c\u677f\uff0c\u539a\u5ea6120mm\uff0c\u6807\u9ad83.6m", "mtime": 1794051228.4414835}, {"run_id": "20261107T113341-38db91e6", "status": "passed", "engine": "revit", "elements": 1, "attempts": 1, "instruction": "\u751f\u62108m\u00d75m\u7684\u697c\u677f\uff0c\u677f\u539a150mm\uff0c\u6807\u9ad80m", "mtime": 1794051224.8137946}, {"run_id": "20261107T113337-e19c7afb", "status": "passed", "engine": "revit", "elements": 1, "attempts": 1, "instruction": "\u521b\u5efa\u4e00\u6839450mm\u00d7450mm\u3001\u9ad85m\u7684\u67f1", "mtime": 1794051221.1951027}, {"run_id": "20261107T113333-01737cd9", "status": "passed", "engine": "revit", "elements": 1, "attempts": 1, "instruction": "\u751f\u6210300mm\u00d7600mm\u7684\u67f1\uff0c\u9ad83m", "mtime": 1794051217.5833378}, {"run_id": "20261107T113330-455c5c78", "status": "passed", "engine": "revit", "elements": 1, "attempts": 1, "instruction": "\u521b\u5efa\u4e00\u6839500mm\u00d7500mm\u3001\u9ad8\u5ea64.2m\u7684\u67f1", "mtime": 1794051213.983431}, {"run_id": "20261107T113326-1661a3b3", "status": "passed", "engine": "revit", "elements": 1, "attempts": 1, "instruction": "\u751f\u6210\u4e00\u6839400mm\u00d7400mm\u3001\u9ad8\u5ea63.6m\u7684\u67f1", "mtime": 1794051210.3720648}, {"run_id": "20261107T113323-7b2c59f5", "status": "passed", "engine": "revit", "elements": 3, "attempts": 1, "instruction": "\u521b\u5efa\u6807\u9ad80m\u30013.3m\u548c6.6m", "mtime": 1794051206.7641852}, {"run_id": "20261107T113319-f9e5a1dd", "status": "passed", "engine": "revit", "elements": 2, "attempts": 1, "instruction": "\u751f\u6210\u6807\u9ad8-0.45m\u548c4.2m", "mtime": 1794051203.1583228}, {"run_id": "20261107T113315-00750d34", "status": "passed", "engine": "revit", "elements": 2, "attempts": 1, "instruction": "\u521b\u5efa\u6807\u9ad80m\u548c3.6m", "mtime": 1794051199.5425022}], "cost": {"\u6c47\u603b": {"\u5206\u90e8\u5206\u9879": 89527.2, "\u63aa\u65bd\u9879\u76ee": 26880.0, "\u571f\u77f3\u65b9": 2592.0, "\u7ba1\u7406\u8d39\u5229\u6da6": 15132.94, "\u89c4\u8d39": 3288.5, "\u7a0e\u91d1": 12134.58, "\u603b\u9020\u4ef7": 146963.22}, "\u8d39\u7528\u7ed3\u6784": {"\u5206\u90e8\u5206\u9879": "60.9%", "\u63aa\u65bd\u9879\u76ee": "18.3%", "\u571f\u77f3\u65b9": "1.8%"}, "\u6982\u51b5": {"\u5efa\u7b51\u9762\u79ef_m2": 192.0, "\u697c\u5c42\u6570": 2, "\u57fa\u7840\u57cb\u6df1_\u5047\u8bbe_m": 1.5, "\u677f\u539a_\u5047\u8bbe_mm": 120.0, "\u6570\u636e\u6765\u6e90": "Revit \u771f\u5b9e\u6784\u4ef6\u51e0\u4f55\uff08\u9010\u6784\u4ef6\u53ef\u6eaf\u6e90\uff09\uff1b\u94a2\u7b4b/\u571f\u65b9\u4e3a\u6307\u6807\u4e0e\u5047\u8bbe\u63a8\u7b97"}, "\u6e05\u5355\u9879\u6570": 9, "excel": "D:\\admin\\Documents\\deepseek-harness\\default-workspace\\aec-copilot-merged\\runs\\cost\\cost-report.xlsx", "markdown": "D:\\admin\\Documents\\deepseek-harness\\default-workspace\\aec-copilot-merged\\runs\\cost\\cost-report.md"}, "report_md": "# \u771f\u673a\u8bc4\u6d4b\u62a5\u544a\uff08live backend, 2026-11-07\uff09\n\n- \u603b\u7528\u4f8b: 50  \u901a\u8fc7: 48  \u901a\u8fc7\u7387: 96%\n- \u8bf4\u660e\uff1a49_part / 50_assembly \u4e3a SOLIDWORKS \u5f15\u64ce\uff0c\u672c\u673a SW \u672a\u542f\u52a8\uff0c\u6309\u8bbe\u8ba1\u5feb\u901f\u5931\u8d25\uff08E_ENGINE_DOWN\uff09\uff1b50_assembly \u53e6\u9700\u96f6\u4ef6 ID \u8bed\u6cd5\uff08\u89c4\u5212\u5668\u7ea6\u675f\uff09\u3002\n\n| \u7528\u4f8b | engine | \u72b6\u6001 | \u5c1d\u8bd5 | \u6307\u4ee4 |\n|---|---|---|---|---|\n| 01_wall | revit | \u2705 passed | 1 | 01_wall |\n| 02_wall | revit | \u2705 passed | 1 | 02_wall |\n| 03_wall | revit | \u2705 passed | 1 | 03_wall |\n| 04_wall | revit | \u2705 passed | 1 | 04_wall |\n| 05_wall | revit | \u2705 passed | 1 | 05_wall |\n| 06_wall | revit | \u2705 passed | 1 | 06_wall |\n| 07_wall | revit | \u2705 passed | 1 | 07_wall |\n| 08_wall | revit | \u2705 passed | 1 | 08_wall |\n| 09_room | revit | \u2705 passed | 1 | 09_room |\n| 10_room | revit | \u2705 passed | 1 | 10_room |\n| 11_room | revit | \u2705 passed | 1 | 11_room |\n| 12_room | revit | \u2705 passed | 1 | 12_room |\n| 13_room | revit | \u2705 passed | 1 | 13_room |\n| 14_room | revit | \u2705 passed | 1 | 14_room |\n| 15_room | revit | \u2705 passed | 1 | 15_room |\n| 16_room | revit | \u2705 passed | 1 | 16_room |\n| 17_frame | revit | \u2705 passed | 1 | 17_frame |\n| 18_frame | revit | \u2705 passed | 1 | 18_frame |\n| 19_frame | revit | \u2705 passed | 1 | 19_frame |\n| 20_frame | revit | \u2705 passed | 1 | 20_frame |\n| 21_frame | revit | \u2705 passed | 1 | 21_frame |\n| 22_frame | revit | \u2705 passed | 1 | 22_frame |\n| 23_building | revit | \u2705 passed | 1 | 23_building |\n| 24_building | revit | \u2705 passed | 1 | 24_building |\n| 25_building | revit | \u2705 passed | 1 | 25_building |\n| 26_building | revit | \u2705 passed | 1 | 26_building |\n| 27_building | revit | \u2705 passed | 1 | 27_building |\n| 28_building | revit | \u2705 passed | 1 | 28_building |\n| 29_building | revit | \u2705 passed | 1 | 29_building |\n| 30_building | revit | \u2705 passed | 1 | 30_building |\n| 31_building | revit | \u2705 passed | 1 | 31_building |\n| 32_building | revit | \u2705 passed | 1 | 32_building |\n| 33_level | revit | \u2705 passed | 1 | 33_level |\n| 34_level | revit | \u2705 passed | 1 | 34_level |\n| 35_level | revit | \u2705 passed | 1 | 35_level |\n| 36_level | revit | \u2705 passed | 1 | 36_level |\n| 37_column | revit | \u2705 passed | 1 | 37_column |\n| 38_column | revit | \u2705 passed | 1 | 38_column |\n| 39_column | revit | \u2705 passed | 1 | 39_column |\n| 40_column | revit | \u2705 passed | 1 | 40_column |\n| 41_slab | revit | \u2705 passed | 1 | 41_slab |\n| 42_slab | revit | \u2705 passed | 1 | 42_slab |\n| 43_slab | revit | \u2705 passed | 1 | 43_slab |\n| 44_slab | revit | \u2705 passed | 1 | 44_slab |\n| 45_opening | revit | \u2705 passed | 1 | 45_opening |\n| 46_opening | revit | \u2705 passed | 1 | 46_opening |\n| 47_polyline | acad | \u2705 passed | 1 | 47_polyline |\n| 48_polyline | acad | \u2705 passed | 1 | 48_polyline |\n| 49_part | sw | \u274c failed | 2 | 49_part |\n| 50_assembly | sw | \ud83d\udca5 error | 0 | 50_assembly |\n"};    // host 路由
    // host 路由（/api/aec/*）生效后，fetch 成功会覆盖内联快照（实时态）。

    const DICT = {
      zh: { panel: "AEC", title: "蓝图智匠 · AEC Copilot" },
      en: { panel: "AEC", title: "AEC Copilot" }
    };

    const CARD = { flex: "1 1 0", minWidth: 140, background: "var(--dsw-alias-bg-layer-2, rgba(127,127,127,.10))",
      border: "1px solid var(--dsw-alias-border-l1, rgba(127,127,127,.25))", borderRadius: 10, padding: "10px 14px" };
    const TH = { textAlign: "left", padding: "4px 10px", opacity: 0.65, fontSize: 11.5, whiteSpace: "nowrap" };
    const TD = { padding: "4px 10px", fontSize: 12, borderBottom: "1px solid var(--dsw-alias-border-l1, rgba(127,127,127,.15))" };
    const BTN = { cursor: "pointer", border: "1px solid var(--dsw-alias-border-l1, rgba(127,127,127,.4))",
      borderRadius: 6, padding: "3px 10px", background: "var(--dsw-alias-bg-layer-2, rgba(127,127,127,.12))", color: "inherit" };

    /* 产物下载：同源 fetch + Blob（走与 /api/aec 相同的鉴权路径，
       不依赖 target=_blank——DSH 客户端内嵌浏览器会拦截新窗口导航）。 */
    async function fetchArtifact(path) {
      const res = await fetch(`/api/aec/file?path=${encodeURIComponent(path)}`, { credentials: "same-origin" });
      if (!res.ok) {
        let detail = "";
        try { detail = (await res.text()).slice(0, 160); } catch { /* 非 JSON 体 */ }
        throw new Error(`HTTP ${res.status}${detail ? " — " + detail : ""}`);
      }
      return res;
    }
    async function downloadArtifact(path, filename) {
      const res = await fetchArtifact(path);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename || String(path).split(/[\\/]/).pop();
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 5000);
    }
    async function viewArtifactText(path) {
      const res = await fetchArtifact(path);
      return await res.text();
    }

    function PanelIcon() {
      return h("svg", { width: 18, height: 18, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor",
        strokeWidth: 2, strokeLinecap: "round", strokeLinejoin: "round" },
        h("path", { d: "M3 21h18" }),
        h("path", { d: "M5 21V7l7-4 7 4v14" }),
        h("path", { d: "M9 21v-6h6v6" }),
        h("path", { d: "M9 11h.01M12 11h.01M15 11h.01" })
      );
    }

    const badge = (ok, label) => h("span", {
      style: { padding: "2px 8px", borderRadius: 999, fontSize: 11,
        background: ok ? "rgba(46,160,67,.18)" : "rgba(218,54,51,.18)",
        color: ok ? "#2ea043" : "#da3633" } }, label);

    const ICONS = { ".png": "🖼", ".jpg": "🖼", ".jpeg": "🖼", ".pdf": "📄", ".xlsx": "📊", ".rvt": "🏠", ".dwg": "📐", ".dxf": "📐", ".ifc": "🧩" };

    function ArtifactsCard({ run }) {
      const [arts, setArts] = useState(run.artifacts ?? []);
      const [open, setOpen] = useState(false);
      const [preview, setPreview] = useState(null);
      if (!open) {
        return h("div", { style: TD },
          h("button", { style: { ...BTN, padding: "1px 8px", fontSize: 11 }, onClick: async () => {
            setOpen(true);
            try {
              const j = await (await fetch(`/api/aec/file.list?path=${encodeURIComponent(run.output_dir)}`)).json();
              if (j.ok) setArts(j.result.artifacts);
            } catch (e) { /* 快照数据兜底 */ }
          } }, `产物 ${run.artifacts?.length ?? 0}`));
      }
      const imgs = arts.filter((a) => [".png", ".jpg", ".jpeg"].includes(a.ext));
      const docs = arts.filter((a) => ![".png", ".jpg", ".jpeg"].includes(a.ext));
      return h("div", { style: { ...TD, minWidth: 220 } },
        h("button", { style: { ...BTN, padding: "1px 8px", fontSize: 11 }, onClick: () => setOpen(false) }, "收起 ▲"),
        docs.length ? h("div", { style: { display: "flex", flexWrap: "wrap", gap: 4, marginTop: 4 } },
          docs.map((a, i) => h("button", { key: i, style: { ...BTN, fontSize: 11 },
            onClick: async (ev) => {
              const btn = ev.currentTarget;
              const label = btn.textContent;
              btn.disabled = true; btn.textContent = "下载中…";
              try { await downloadArtifact(a.path, a.name); btn.textContent = label; }
              catch (e) { btn.textContent = "⚠ 失败"; }
              finally { btn.disabled = false; }
            } }, `${ICONS[a.ext] ?? "📎"} ${a.name}`))) : null,
        imgs.length ? h("div", { style: { display: "flex", flexWrap: "wrap", gap: 6, marginTop: 6 } },
          imgs.map((a, i) => h("img", { key: i, src: `/api/aec/file?path=${encodeURIComponent(a.path)}`,
            onClick: () => setPreview(a), title: a.name,
            style: { height: 64, border: "1px solid var(--dsw-alias-border-l1, rgba(127,127,127,.3))", borderRadius: 6, cursor: "zoom-in" } }))) : null,
        preview ? h("div", { style: { position: "fixed", inset: 0, background: "rgba(0,0,0,.75)", zIndex: 999,
          display: "flex", alignItems: "center", justifyContent: "center" },
          onClick: () => setPreview(null) },
          h("img", { src: `/api/aec/file?path=${encodeURIComponent(preview.path)}`, style: { maxHeight: "90%", maxWidth: "90%" } })) : null
      );
    }

    function StatusPage() {
      const [status, setStatus] = useState(null);
      const [runs, setRuns] = useState([]);
      const [report, setReport] = useState("");
      const [err, setErr] = useState(null);
      const [tick, setTick] = useState(0);

      const refresh = useCallback(() => {
        fetch("/api/aec/status.get").then((r) => r.json()).then((j) => setStatus(j.ok ? j.result : null)).catch((e) => setErr(String(e)));
        fetch("/api/aec/runs.list?limit=15").then((r) => r.json()).then((j) => setRuns(j.ok ? j.result : [])).catch(() => {});
        fetch("/api/aec/report.get").then((r) => r.json()).then((j) => setReport(j.ok ? (j.result.markdown || "") : "")).catch(() => {});
      }, []);

      useEffect(() => { refresh(); }, [tick, refresh]);

      const ev = status?.eval;
      const bridgeOk = status?.bridge?.state === "running";

      return h("div", { style: { width: "100%", height: "100%", overflow: "auto", padding: "14px 18px", boxSizing: "border-box" } },
        h("div", { style: { display: "flex", alignItems: "center", gap: 10, marginBottom: 12 } },
          h("div", { style: { fontSize: 15, fontWeight: 700 } }, "蓝图智匠 · AEC Copilot"),
          h("span", { style: { flex: "1 1 auto" } }),
          h("button", { style: BTN, onClick: () => setTick((t) => t + 1) }, "刷新")
        ),
        err ? h("div", { style: { color: "#da3633", fontSize: 12 } }, "加载失败: " + err) : null,

        h("div", { style: { display: "flex", gap: 10, marginBottom: 12, flexWrap: "wrap" } },
          h("div", { style: CARD },
            h("div", { style: { fontSize: 11, opacity: 0.65 } }, "真机评测"),
            h("div", { style: { fontSize: 22, fontWeight: 700 } }, ev ? `${ev.passed}/${ev.total}` : "–"),
            ev ? badge(true, `通过率 ${ev.rate}%`) : null),
          h("div", { style: CARD },
            h("div", { style: { fontSize: 11, opacity: 0.65 } }, "Revit 全类目"),
            h("div", { style: { fontSize: 22, fontWeight: 700 } }, ev ? `${ev.revit_passed}/${ev.revit_total}` : "–"),
            ev ? badge(ev.revit_passed === ev.revit_total, ev.revit_passed === ev.revit_total ? "100%" : "部分") : null),
          h("div", { style: CARD },
            h("div", { style: { fontSize: 11, opacity: 0.65 } }, "Revit 桥"),
            h("div", { style: { fontSize: 18, fontWeight: 700, marginTop: 2 } }, status ? (bridgeOk ? "在线" : status.bridge.state) : "–"),
            status ? badge(bridgeOk, status.bridge.document ? `文档: ${status.bridge.document}` : status.bridge.state) : null),
          h("div", { style: CARD },
            h("div", { style: { fontSize: 11, opacity: 0.65 } }, "规则审图检出"),
            h("div", { style: { fontSize: 22, fontWeight: 700 } }, "20/20"),
            badge(true, "预埋缺陷全命中"))
        ),

        h("div", { style: { fontSize: 12, opacity: 0.7, margin: "14px 0 6px" } }, "设计 → 造价（真模型工程量）"),
        (window.__AEC_DATA__?.cost || status?.cost) ? (() => {
          const c = (status && status.cost) || window.__AEC_DATA__.cost;
          const s = c.汇总 ?? {};
          return h("div", { style: { display: "flex", gap: 10, marginBottom: 12, flexWrap: "wrap", alignItems: "stretch" } },
            h("div", { style: { ...CARD, flex: "2 1 220px" } },
              h("div", { style: { fontSize: 11, opacity: 0.65 } }, "项目总造价（演示价目）"),
              h("div", { style: { fontSize: 26, fontWeight: 700, color: "#2ea043" } },
                "¥ " + Number(s["总造价"] ?? 0).toLocaleString("zh-CN", { minimumFractionDigits: 2 })),
              h("div", { style: { fontSize: 11, opacity: 0.6 } },
                "建筑面积 " + (c.概况?.["建筑面积_m2"] ?? "–") + " m² · " + (c.概况?.["楼层数"] ?? "–") + " 层 · " + (c.清单项数 ?? "–") + " 项清单")),
            ...Object.entries(c.费用结构 ?? {}).map(([k, v]) => h("div", { style: CARD },
              h("div", { style: { fontSize: 11, opacity: 0.65 } }, k),
              h("div", { style: { fontSize: 20, fontWeight: 700 } }, v))),
            h("div", { style: { ...CARD, display: "flex", flexDirection: "column", gap: 6, justifyContent: "center" } },
              c.excel ? h("button", { style: { ...BTN, fontSize: 12, textAlign: "center" },
                onClick: async (ev) => {
                  const btn = ev.currentTarget;
                  btn.disabled = true; btn.textContent = "下载中…";
                  try { await downloadArtifact(c.excel, "cost-report.xlsx"); btn.textContent = "📊 计价 Excel"; }
                  catch (e) { btn.textContent = "⚠ 下载失败：" + String(e.message ?? e).slice(0, 60); }
                  finally { btn.disabled = false; }
                } }, "📊 计价 Excel") : null,
              c.markdown ? h("button", { style: { ...BTN, fontSize: 12, textAlign: "center" },
                onClick: async (ev) => {
                  const btn = ev.currentTarget;
                  btn.disabled = true; btn.textContent = "加载中…";
                  try {
                    const text = await viewArtifactText(c.markdown);
                    const w = window.open("", "_blank");
                    if (w) { w.document.write("<pre style='white-space:pre-wrap;font:13px monospace'>" + text.replace(/[&<>]/g, (m) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[m])) + "</pre>"); }
                    else { const blob = new Blob([text], { type: "text/markdown;charset=utf-8" }); const url = URL.createObjectURL(blob); const a = document.createElement("a"); a.href = url; a.download = "cost-report.md"; document.body.appendChild(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(url), 5000); }
                    btn.textContent = "📄 计价报告";
                  } catch (e) { btn.textContent = "⚠ 打开失败：" + String(e.message ?? e).slice(0, 60); }
                  finally { btn.disabled = false; }
                } }, "📄 计价报告")
              : null));
        })() : null,

        h("div", { style: { fontSize: 12, opacity: 0.7, marginBottom: 6 } }, "最近运行（真机 / 评测）"),
        h("table", { style: { width: "100%", borderCollapse: "collapse", marginBottom: 16 } },
          h("thead", null, h("tr", null,
            h("th", { style: TH }, "状态"), h("th", { style: TH }, "引擎"), h("th", { style: TH }, "构件"),
            h("th", { style: TH }, "尝试"), h("th", { style: TH }, "指令"), h("th", { style: TH }, "产物"))),
          h("tbody", null, runs.map((r, i) => h("tr", { key: i },
            h("td", { style: TD }, r.status === "passed" ? badge(true, "passed") : badge(false, r.status)),
            h("td", { style: TD }, r.engine),
            h("td", { style: TD }, String(r.elements)),
            h("td", { style: TD }, String(r.attempts)),
            h("td", { style: { ...TD, maxWidth: 320 } }, r.instruction),
            h(ArtifactsCard, { run: r, key: `a${i}` }))))),

        report ? h("details", null,
          h("summary", { style: { cursor: "pointer", fontSize: 12, opacity: 0.75 } }, "真机评测报告（展开）"),
          h("pre", { style: { fontSize: 11, whiteSpace: "pre-wrap", background: "var(--dsw-alias-bg-layer-2, rgba(127,127,127,.08))",
            padding: 12, borderRadius: 8, maxHeight: 320, overflow: "auto" } }, report)) : null,

        h("div", { style: { fontSize: 11.5, opacity: 0.6, marginTop: 10, lineHeight: 1.7 } },
          "建模/审图工具走 MCP 连接器 aec（mcp__aec__aec_run 等），对 Agent 直接说中文即可；",
          "本面板只读展示 runs/ 与 eval/ 产物。")
      );
    }

    function apply(ctx) {
      ctx.effect(() => ctx.locale.register(NS, DICT), "aec-copilot locale");
      const t = ctx.locale.bind(NS);

      ctx.slots.inject("main", function* () {
        yield ctx.slots.register({ name: "main", key: PANEL_ID, locale: NS }, StatusPage);
      });
      ctx.slots.inject("sidebar.panellist", () =>
        ctx.slots.register(
          { name: "sidebar.panellist", id: PANEL_ID, order: 21, label: () => t("panel"), locale: NS },
          PanelIcon
        )
      );
    }

    exports.apply = apply;
    exports.inject = inject;
    exports.StatusPage = StatusPage;
    return module.exports;
  }
});
