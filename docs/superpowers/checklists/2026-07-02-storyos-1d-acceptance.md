# StoryOS Phase 1D 验收清单

> 完成日期：__________  验收人：__________
>
> 说明：1D 为「前端 + API」里程碑。cascade simulate/replay 与 migration
> 端点在 1D 为**桩实现**（返回 501 NOT_IMPLEMENTED），真实逻辑在 1E 接入。
> 下方标注 `(1D 桩)` 的项以 501 为通过标准。

## A. 功能验收（100% 必须通过）

### A.1 API 端点

- [ ] 40 CRUD 端点全 200/201/204（8 entity × 5 操作）
- [ ] 3 cascade 端点：simulate 501 `(1D 桩)` / replay 501 `(1D 桩)` / history 200
- [ ] 2 sflog 端点：raw 200 / reparse 200（1D 桩返回零计数）
- [ ] 2 migration 端点：501 `(1D 桩)` + OpenAPI schema 可见
- [ ] 2 health/metrics 端点：200 + 6 指标齐全
- [ ] 错误路径覆盖：422/404 + ErrorResponse envelope

### A.2 Frontend

- [ ] StoryOSHub 主面板可访问
- [ ] 6 子视图全部可用
- [ ] 4 组件渲染正确
- [ ] 3 Pinia stores 状态同步
- [ ] PredeclaredDiff 三色高亮
- [ ] i18n 中文文案完整

## B. 集成验收

- [ ] 完整 happy path 端到端（`tests/e2e/test_storyos_workbench_flow.py`）
- [ ] 与 1C 引擎钩子串联（`tests/integration/api/v1/storyos/test_engine_hook_integration.py`）
- [ ] Export DOCX 不含 SF_LOG 注释（`infrastructure/export/docx_exporter.py`）
- [ ] OpenAPI schema 完整

## C. 性能基准

- [ ] 8 registry 列表 < 200ms
- [ ] CascadeGraph 渲染 < 500ms（1D 冒烟测空态挂载；100 节点基准在 1F）
- [ ] SFLogInspector 解析 < 200ms
- [ ] StoryOSHub 首屏 TTI < 1s
- [ ] storyos-vendor chunk < 500KB（`python scripts/check_storyos_chunk_size.py`）

## D. 用户验收

- [ ] Workbench "StoryOS" 入口可见
- [ ] 5 子视图路由可达
- [ ] Migration 端点显示"功能开发中"

## E. 文档

- [ ] CLAUDE.md 更新
- [ ] README 更新（如适用）
- [ ] OpenAPI 文档可访问
- [ ] 验收清单签收
