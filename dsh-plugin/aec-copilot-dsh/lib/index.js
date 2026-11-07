/**
 * AEC Copilot（蓝图智匠）— DSH 宿主半侧插件
 *
 * 注册 /aec/api 前缀路由（鉴权围栏与官方 /api 网关一致）：
 *  - /aec/api/status   三引擎状态 + 桥心跳 + 评测摘要（纯文件读取，无 Python 依赖）
 *  - /aec/api/runs     最近运行一览（merged runs + eval/results-live runs）
 *  - /aec/api/report   真机评测报告（Markdown 原文）
 *
 * 客户端半侧见 client.js（dsh.client 声明，由 dsh-client-modules 提供）。
 */
import { existsSync, readFileSync, readdirSync, statSync, appendFileSync } from 'node:fs';
import path from 'node:path';

// 加载探针：模块被 cordis 加载时立刻留痕（区分「模块没加载」vs「apply 没跑」）
const _probe = path.join(path.dirname(fileURLToPath(import.meta.url)), '..', 'host-load.log');
try {
  appendFileSync(_probe, `loaded ${new Date().toISOString()} url=${import.meta.url}\n`);
} catch { /* 只读环境忽略 */ }

export const name = 'aec-copilot-dsh';

/** 插件激活前必须就位的服务（与录阶完全一致）。 */
export const inject = ['webServer', 'connection'];

function resolveConfig(config = {}) {
  return {
    repoRoot: config.repoRoot ?? 'D:/admin/Documents/deepseek-harness/default-workspace/aec-copilot-merged',
    bridgeRoot: config.bridgeRoot ?? path.join(process.env.LOCALAPPDATA ?? '', 'RevitCommandBridge', '2024'),
  };
}

function readJsonSafe(file) {
  try {
    if (!existsSync(file)) return null;
    return JSON.parse(readFileSync(file, 'utf8'));
  } catch {
    return null;
  }
}

function listRuns(runsDir, limit = 20) {
  const dir = path.join(runsDir, 'runs');
  if (!existsSync(dir)) return [];
  const rows = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    if (!entry.isDirectory()) continue;
    const runJson = path.join(dir, entry.name, 'run.json');
    const data = readJsonSafe(runJson);
    if (!data) continue;
    rows.push({
      run_id: data.run_id ?? entry.name,
      status: data.status,
      engine: data.engine,
      instruction: String(data.instruction ?? '').slice(0, 60),
      elements: (data.elements ?? []).length,
      attempts: (data.attempts ?? []).length,
      output_dir: data.output_dir ?? path.dirname(runJson),
      mtime: statSync(runJson).mtimeMs,
    });
  }
  return rows.sort((a, b) => b.mtime - a.mtime).slice(0, limit);
}

function buildApi({ repoRoot, bridgeRoot }) {
  const evalLive = path.join(repoRoot, 'eval', 'results-live');
  return {
    async 'status.get'() {
      const bridge = readJsonSafe(path.join(bridgeRoot, 'status.json')) ?? { state: 'unknown' };
      const results = readJsonSafe(path.join(evalLive, 'results.json'));
      const latest = {};
      if (results?.results) {
        for (const r of results.results) latest[r.id] = r; // 最近一次结果
        const rows = Object.values(latest);
        const n = rows.length;
        const pass = rows.filter((r) => r.status === 'passed').length;
        const revit = rows.filter((r) => r.engine === 'revit');
        latest.__summary = {
          total: n,
          passed: pass,
          rate: n ? Math.round((pass / n) * 100) : 0,
          revit_total: revit.length,
          revit_passed: revit.filter((r) => r.status === 'passed').length,
        };
      }
      const reportExists = existsSync(path.join(evalLive, 'report.md'));
      return {
        bridge: { state: bridge.state, document: bridge.data?.document_title ?? null, heartbeat_age_s: null },
        eval: latest.__summary ?? null,
        artifacts: {
          eval_report: reportExists ? path.join(evalLive, 'report.md') : null,
          ifc_demo: existsSync(path.join(repoRoot, 'out')) ? path.join(repoRoot, 'out') : null,
        },
        tools_hint: 'MCP 连接器 aec：mcp__aec__aec_run / aec_preview / aec_audit …',
      };
    },
    async 'runs.list'(args) {
      const limit = Math.min(Number(args?.limit) || 20, 50);
      const main = listRuns(repoRoot, limit);
      const evalRuns = listRuns(evalLive, limit);
      const seen = new Set();
      return [...main, ...evalRuns]
        .filter((r) => (seen.has(r.run_id + r.output_dir) ? false : (seen.add(r.run_id + r.output_dir), true)))
        .slice(0, limit);
    },
    async 'report.get'() {
      const file = path.join(evalLive, 'report.md');
      if (!existsSync(file)) return { markdown: '# 暂无报告' };
      return { markdown: readFileSync(file, 'utf8') };
    },
  };
}

export function apply(ctx, config) {
  const cfg = resolveConfig(config);
  const api = buildApi(cfg);
  // 与官方 /api 网关相同的连接鉴权围栏；connection 服务缺失时拒绝所有请求（录阶同语义）。
  const fence = (req) => (ctx.connection?.requestRejection ? ctx.connection.requestRejection(req) === undefined : false);
  try {
    appendFileSync(_probe, `apply entered ${new Date().toISOString()} connection=${typeof ctx.connection}\n`);
  } catch { /* 只读环境忽略 */ }

  ctx.effect(
    () =>
      ctx.webServer.register({
        kind: 'prefix',
        path: '/aec/api',
        handler: async (req, res) => {
          if (!fence(req)) {
            res.writeHead(403, { 'content-type': 'application/json' });
            res.end(JSON.stringify({ ok: false, error: { code: 'forbidden', message: 'forbidden' } }));
            return;
          }
          const url = new URL(req.url ?? '/', 'http://dsh.internal');
          const method = url.pathname.startsWith('/aec/api/') ? url.pathname.slice('/aec/api/'.length) : '';
          const handler = method && Object.hasOwn(api, method) ? api[method] : undefined;
          if (typeof handler !== 'function') {
            res.writeHead(404, { 'content-type': 'application/json' });
            res.end(JSON.stringify({ ok: false, error: { code: 'not-found', message: `未知方法 "${method}"` } }));
            return;
          }
          try {
            const args = req.method === 'GET' ? Object.fromEntries(url.searchParams) : await new Promise((resolve, reject) => {
              let body = '';
              req.on('data', (c) => (body += c));
              req.on('end', () => { try { resolve(body ? JSON.parse(body) : {}); } catch (e) { reject(e); } });
              req.on('error', reject);
            });
            const result = await handler(args);
            res.writeHead(200, { 'content-type': 'application/json' });
            res.end(JSON.stringify({ ok: true, result }));
          } catch (error) {
            res.writeHead(500, { 'content-type': 'application/json' });
            res.end(JSON.stringify({ ok: false, error: { code: 'error', message: String(error?.message ?? error) } }));
          }
        },
      }),
    'aec-copilot-dsh: /aec/api routes',
  );

  ctx.logger?.info?.(`aec-copilot-dsh: 已挂载 /aec/api（repoRoot=${cfg.repoRoot}）`);
}
