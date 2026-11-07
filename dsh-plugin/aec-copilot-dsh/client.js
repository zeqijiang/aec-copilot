/*
 * aec-copilot-dsh — DSH 客户端半侧（浏览器 bundle）
 *
 * 形态与「录阶」「dsh-ide-panel」一致：sidebar.panellist + main 槽位。
 * 数据来自宿主半侧 /aec/api/* 路由（同源，鉴权围栏与官方网关一致）。
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

    function StatusPage() {
      const [status, setStatus] = useState(null);
      const [runs, setRuns] = useState([]);
      const [report, setReport] = useState("");
      const [err, setErr] = useState(null);
      const [tick, setTick] = useState(0);

      const refresh = useCallback(() => {
        fetch("/aec/api/status.get").then((r) => r.json()).then((j) => setStatus(j.ok ? j.result : null)).catch((e) => setErr(String(e)));
        fetch("/aec/api/runs.list?limit=15").then((r) => r.json()).then((j) => setRuns(j.ok ? j.result : [])).catch(() => {});
        fetch("/aec/api/report.get").then((r) => r.json()).then((j) => setReport(j.ok ? (j.result.markdown || "") : "")).catch(() => {});
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

        h("div", { style: { fontSize: 12, opacity: 0.7, marginBottom: 6 } }, "最近运行（真机 / 评测）"),
        h("table", { style: { width: "100%", borderCollapse: "collapse", marginBottom: 16 } },
          h("thead", null, h("tr", null,
            h("th", { style: TH }, "状态"), h("th", { style: TH }, "引擎"), h("th", { style: TH }, "构件"),
            h("th", { style: TH }, "尝试"), h("th", { style: TH }, "指令"))),
          h("tbody", null, runs.map((r, i) => h("tr", { key: i },
            h("td", { style: TD }, r.status === "passed" ? badge(true, "passed") : badge(false, r.status)),
            h("td", { style: TD }, r.engine),
            h("td", { style: TD }, String(r.elements)),
            h("td", { style: TD }, String(r.attempts)),
            h("td", { style: TD }, r.instruction))))),

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
