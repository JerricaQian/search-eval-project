export const meta = {
  name: 'meituan-search-eval',
  description: '美团搜索结果页 标准化评测 Agent：截图→Phase2/3/4/5 单词全链路子代理→合并HTML报告',
  phases: [
    { title: '① 截图', detail: 'ADB现场截图或复用已有图，9张/词' },
    { title: '② 发现评测项', detail: '自动发现所选维度的 eval skill（纯 frontmatter 解析，JS 级并行）' },
    { title: '③ Phase2+3+4+5 单词全链路', detail: '单图本地识别→多维度评测→问题证据→报告渲染，四阶段在同一子代理内顺序完成' },
    { title: '④ Manifest 质量侧审计', detail: '可选：单图元素清单 L1/L2/L3 合规率统计，仅记录不阻断' },
  ],
}

// ---------- 参数 ----------
let A = args
if (typeof A === 'string') { try { A = JSON.parse(A) } catch (e) { A = {} } }
if (!A || typeof A !== 'object') A = {}
log('args=' + JSON.stringify(A))
log('批量调度纪律：当前实例仅处理 1 个搜索词；外层每批最多 3 个词级子代理，必须批次屏障后再继续。')

// Phase2 本身只运行本地 CV/OCR；同一子代理在后续 Phase3/4 仍需核对截图与问题证据，故模型须具备多模态能力。
// 白名单以 Dr. Pie 模型目录中已验证具备识图能力的模型为准（该目录当前未收录 Gemini 系列）；
// 非多模态模型（如 glm-5.2、deepseek 系列）路由到读图任务会导致结构化输出/图像理解异常，不得使用。
const MULTIMODAL_MODEL_WHITELIST = ['claude-sonnet-5', 'vertex.claude-opus-4.6', 'kimi-k3', 'gpt-5.6-terra']
const SUBAGENT_MODEL = A.model ? A.model : 'claude-sonnet-5'
if (!MULTIMODAL_MODEL_WHITELIST.includes(SUBAGENT_MODEL)) {
  throw new Error('SUBAGENT_MODEL="' + SUBAGENT_MODEL + '" 不在多模态识图模型白名单内（' + MULTIMODAL_MODEL_WHITELIST.join('/') + '）；本工作流全程依赖识图，禁止使用非多模态模型')
}
// 批量编排铁律：外层调用方必须把搜索词切为单词任务；每批最多 3 个词级子代理，
// 必须等待本批完成再派下一批。当前工作流实例只接受并处理一个 query，绝不在内部混跑多词。
const MAX_QUERY_AGENTS_PER_BATCH = 3
const SINGLE_QUERY_PER_AGENT = true

// 此工作流是严格的单词执行单元。批量词必须由外层调度器切分为独立实例，
// 依次按每批最多 3 个实例运行并等待批次屏障；不得把 queries 直接注入本实例。
if (Array.isArray(A.queries)) {
  throw new Error('当前工作流只接受单个 query；请由外层调度器将 queries 切分为单词任务（每批最多 3 个，等待整批完成后再派下一批）')
}
if (!A.query || typeof A.query !== 'string' || !A.query.trim()) {
  throw new Error('当前工作流必须显式传入非空字符串 query')
}
const query = A.query.trim()
const tabs = A.tabs ? A.tabs : ['全部', '外卖', '团购']
const screens = A.screens ? A.screens : ['1', '2', '3']
const skipScreenshot = A.skipScreenshot === false ? false : true
// 维度文件夹名数组（顶层目录下的维度目录）。默认只跑 phase3-card_or_component-eval。
let dimensions = A.dimensions ? A.dimensions : ['phase3-card_or_component-eval']
if (typeof dimensions === 'string') dimensions = [dimensions]
// Phase2 只允许轻量识别，并为每张截图产出一个独立 JSON。annotate=false 才显式跳过。
const annotate = A.annotate === false ? false : true
const skipAnnotation = !annotate
const phase2Mode = A.phase2Mode ? A.phase2Mode : 'lightweight'
if (phase2Mode !== 'lightweight') throw new Error('phase2Mode 当前只允许 lightweight；Phase2 不再生成整页标注图，收到: ' + phase2Mode)
if (A.imdLink) throw new Error('标准 Phase2 只接受本地截图，不执行 IMD 识别')
const annotateScenes = A.annotateScenes ? A.annotateScenes : []
if (!Array.isArray(annotateScenes)) throw new Error('annotateScenes 必须是截图绝对路径数组')
if (annotateScenes.length) throw new Error('annotateScenes 已停用：Phase2 必须为本轮每张 screenshots 输入分别生成 manifest')
// granularity：Phase3 三个维度都以统一最小元素清单为单一事实源；合并后的 phase2345-query-pipeline agent
// 固定按元素级契约（八键单图清单/regions/elements）执行，不再支持 component/region 颗粒度。
const granularity = A.granularity ? A.granularity : 'element'
if (granularity !== 'element') throw new Error('当前标准工作流只接受 granularity=element；组件/卡片与页面框架评测也必须消费同一份最小元素清单，再按各 Skill 聚合')
const enableAnnotationAudit = A.enableAnnotationAudit !== false
// tag：同一截图需要保留不同批次识别时作为单图 manifest 后缀；截图文件名本身用于区分多图。
const tag = A.tag ? A.tag : ''
const tagSuffix = tag ? '_' + tag : ''

if (!A.projectDir) throw new Error('必须显式传入 projectDir（项目根绝对路径），不再提供兜底默认值')
const projectDir = A.projectDir
const screenshotDir = (A.screenshotDir ? A.screenshotDir : projectDir + '/screenshots')
// annotatedDir：Phase2 单图元素清单输出目录；Phase2 不生成整页标注 PNG。
const annotatedDir = (A.annotatedDir ? A.annotatedDir : projectDir + '/screenshots-out')
const reportDir = (A.reportDir ? A.reportDir : projectDir + '/reports')
// 过程文件与最终 HTML 分离：报告目录只放交付物，评测原始结果和审计记录归档到易识别的过程文件目录。
// 过程产物只追加保留，禁止删除、unlink 或覆盖清理；无效/失败文件也必须保留并记录路径。
const evaluationArtifactDir = projectDir + '/.artifacts/过程文件-评测结果与审计'
const batchId = A.batchId ? A.batchId : '单词运行'
// rerunId 由调用方显式传入，以在同一批次多轮返工时保留独立审计；缺省时复用稳定 batchId，禁止依赖时间或随机数。
const rerunId = A.rerunId ? A.rerunId : batchId
const batchArtifactDir = evaluationArtifactDir + '/' + batchId
const artifactRunDir = batchArtifactDir + '/' + query + tagSuffix
const dimSlug = dimensions.map(d => d.replace(/^phase3-/, '').replace(/-eval$/, '')).join('_')
// 批量治理看板可读取调用方显式给定的当前 batchArtifactDir，但不得借 queries 在本实例内混跑多词。
const isBatchGovernanceReport = A.batchGovernance === true
if (isBatchGovernanceReport && !A.batchId) throw new Error('批量治理报告必须显式传入 batchId，以隔离本批过程产物与治理数据集')
const reportPath = isBatchGovernanceReport
  ? reportDir + '/meituan_search_experience_dashboard_' + query + tagSuffix + '.html'
  : reportDir + '/meituan_eval_report_' + query + tagSuffix + '_' + dimSlug + '.html'
const shotSkillDir = (A.shotSkillDir ? A.shotSkillDir : projectDir + '/phase1-screenshot')
const imdSkillDir = (A.imdSkillDir ? A.imdSkillDir : projectDir + '/phase2-card-annotation')
const issueEvidenceSkillDir = (A.issueEvidenceSkillDir ? A.issueEvidenceSkillDir : projectDir + '/phase4-issue-evidence')
const reportSkillDir = (A.reportSkillDir ? A.reportSkillDir : projectDir + '/phase5-report')
// 每个维度的 eval-skills 目录：projectDir/<dimension>/eval-skills
function skillBaseFor(dim) { return projectDir + '/' + dim + '/eval-skills' }

// ---------- schemas ----------
const SHOT_SCHEMA = {
  type: 'object',
  properties: {
    ok: { type: 'boolean' },
    screenshots: { type: 'array', items: { type: 'string' } },
    error: { type: 'string' },
  },
  required: ['ok', 'screenshots'],
}
const DISCOVERY_SCHEMA = {
  type: 'object',
  properties: {
    dimension: { type: 'string' },
    skills: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          skill: { type: 'string' },
          title: { type: 'string' },
          weight: {
            type: 'object',
            properties: {
              '优秀': { type: 'number' },
              '达标': { type: 'number' },
              '不达标': { type: 'number' },
            },
            required: ['优秀', '不达标'],
          },
          aggregate: { type: 'string' },
          extra: { type: 'string' },
        },
        required: ['skill', 'title', 'weight', 'aggregate', 'extra'],
      },
    },
  },
  required: ['dimension', 'skills'],
}
// ANNOTATE_AUDIT_SCHEMA：仅用于 Phase2b 之外、纯 stdout 转录的辅助侧审计调用（L1/L2/L3 合规率统计）。
const ANNOTATE_AUDIT_SCHEMA = {
  type: 'object',
  properties: {
    stdout: { type: 'string' },
  },
  required: ['stdout'],
}
// PIPELINE_SCHEMA：phase2345-query-pipeline agentType 的统一输出契约，覆盖原 Phase2/3/4/5 四个独立 schema。
const PIPELINE_SCHEMA = {
  type: 'object',
  properties: {
    ok: { type: 'boolean' },
    query: { type: 'string' },
    stageA: {
      type: 'object',
      properties: {
        elementListPaths: { type: 'array', items: { type: 'string' } },
        elementAuditPaths: { type: 'array', items: { type: 'string' } },
        elementCount: { type: 'number' },
        annotated: { type: 'array', items: { type: 'string' } },
      },
      required: ['elementListPaths', 'elementAuditPaths', 'elementCount', 'annotated'],
    },
    stageB: {
      type: 'object',
      properties: {
        evalResultFile: { type: 'string' },
        evalAuditFile: { type: 'string' },
        evalCount: { type: 'number' },
      },
    },
    stageC: {
      type: 'object',
      properties: {
        evidenceImages: { type: 'array', items: { type: 'string' } },
        skipped: { type: 'array' },
      },
    },
    stageD: {
      type: 'object',
      properties: {
        reportPath: { type: 'string' },
        summary: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              tab: { type: 'string' },
              normalizedScore: { type: 'number' },
              verdict: { type: 'string' },
            },
            required: ['tab', 'normalizedScore', 'verdict'],
          },
        },
      },
    },
    blockedAt: { type: 'string' },
    error: { type: 'string' },
  },
  required: ['ok', 'query'],
}

// ---------- Phase 1: 截图 ----------
phase('截图')
log('工作流步骤：① 截图 → ② 发现评测项 → ③ Phase2+3+4+5 单词全链路子代理 → ④ Manifest 质量侧审计（可选）')
log('Phase 1 截图: query=' + query + ' skip=' + skipScreenshot)

const shotPrompt = `你是美团搜索截图执行 Agent。任务：为搜索词「${query}」获取 ${tabs.join('/')} × 第${screens.join('/')}屏 截图，目录 ${screenshotDir}。

${skipScreenshot ? `## 跳过截图模式（用已有截图，禁止运行 run_scroll.sh）
用 Bash 执行：
  ls -la ${screenshotDir}/${query}_*.png 2>/dev/null
对每个 tab×屏 组合（tab∈{${tabs.join(',')}}，屏∈{${screens.join(',')}}）用 stat -f%z 校验文件存在且 >5000 字节。
- 命名格式 ${query}_{tab}_{屏}.png
- 把所有存在且 >5000 字节的文件绝对路径收集到 screenshots 数组返回，ok=true
- 若某个 tab 一个有效文件都没有，ok=false，error 列出缺失项
- 个别屏缺失（如缺第2/3屏但第1屏在）不影响 ok，只需在 error 字段备注哪些屏缺失，仍返回已有的路径
禁止覆盖或删除任何已有文件。` : `## 现场截图模式
设备：Android 手机，USB 连 Mac、USB调试开启、美团App已登录。
⚠️ 坐标依赖机型：run_scroll.sh 的坐标按华为 ABR-AL80（1224×2700）校准。若机型不同，先读 ${shotSkillDir}/SKILL.md 的坐标表，用 adb shell uiautomator dump 校准搜索框/tab/返回按钮坐标后再跑。

⚠️ 关键守卫：设备离线时 run_scroll.sh 会写出 0 字节文件覆盖已有图。因此启动脚本前必须确认设备在线。

步骤（全部用 Bash 工具）：
1. 重连设备：循环最多15次 \`adb kill-server; adb start-server; sleep 1.5\` 直到 \`adb get-state\` 输出 device。
2. 设备在线守卫（必做）：\`adb get-state\` 必须输出 \`device\`。若仍不是 device，立即 ok=false 返回，error="设备离线，未运行截图脚本（避免覆盖）"，**不要执行后续步骤**。
3. 切输入法：\`adb shell ime set com.android.adbkeyboard/.AdbIME\`
4. 启动截图脚本（后台，用 OUT 环境变量指定输出到项目 screenshots 目录）：
   cd ${shotSkillDir} && OUT=${screenshotDir} nohup bash scripts/run_scroll.sh "${query}" "${tabs.join(',')}" "${screens.join(',')}" > /tmp/scroll_run.out 2>&1 &
   echo $! > /tmp/scroll.pid
5. 等待完成（单次 Bash 调用，timeout 设 600000ms）：
   until grep -q ALL_DONE /tmp/meituan_scroll.log 2>/dev/null; do sleep 10; done
6. 校验：\`ls -la ${screenshotDir}/${query}_*.png\`，只收集 >5000 字节的文件；0 字节文件不得删除。将其复制到 \`${artifactRunDir}/phase1/invalid-screenshots/\` 并在 error 字段记录原路径与原因，原文件也保留。
7. 返回 ok=true + 有效文件的绝对路径列表；检查 \`grep '!!' /tmp/meituan_scroll.log\` 有无跳过，有则在 error 备注。若某 tab 无任何有效文件，ok=false。`}

严格按 schema 输出。`

const shotResult = await agent(shotPrompt, { label: '截图', phase: '截图', schema: SHOT_SCHEMA, model: SUBAGENT_MODEL })
if (!shotResult || !shotResult.ok) {
  throw new Error('截图阶段失败: ' + (shotResult && shotResult.error ? shotResult.error : 'agent 无返回'))
}
const screenshots = shotResult.screenshots
log('Phase 1 完成: ' + screenshots.length + ' 张截图')

// ---------- Phase2 固定产物路径：每张截图一个主 JSON，禁止多图合并 ----------
const phase2InputPaths = screenshots
const phase2Outputs = phase2InputPaths.map(p => {
  const stem = p.split('/').pop().replace(/\.[^.]+$/, '')
  const manifest = annotatedDir + '/elements_' + stem + tagSuffix + '.json'
  return {
    screenshot: p,
    manifest,
    audit: manifest.replace(/\.json$/, '.audit.json'),
    recognitionAudit: manifest.replace(/\.json$/, '.recognition-audit.json'),
    artifactsDir: artifactRunDir + '/phase2/' + stem + tagSuffix,
  }
})
if (new Set(phase2Outputs.map(item => item.manifest)).size !== phase2Outputs.length) {
  throw new Error('screenshots 中存在同名文件，无法保证一图一 JSON；请先让截图文件名唯一')
}
const phase2RereviewAuditFile = annotatedDir + '/elements_' + query + tagSuffix + '.recognition-audit-rereview-' + rerunId + '.json'
const phase2RereviewValidationFile = evaluationArtifactDir + '/Phase2返工复核校验_' + query + tagSuffix + '_' + dimSlug + '.json'

const reportImages = screenshots.map(p => ({ original: p, annotated: '' }))

// ---------- Phase 2b: 自动发现各维度 eval skill（纯 frontmatter 解析，不读图，保留 JS 级并行） ----------
phase('评测')
log('Phase 2b 发现: dimensions=' + dimensions.join(','))

const discoveryResults = await parallel(dimensions.map(dim => () => {
  const prompt = `你是评测 skill 发现 Agent。任务：扫描维度目录，用 python 确定性解析每个 eval skill 的 frontmatter，输出 JSON。

⚠️ 注意：weight 中的「达标」键是可选的。二档评测项（只有优秀/不达标）的 SKILL.md frontmatter 可能不含「达标」键，脚本会用 .get("达标",0) 兜底为 0，这类 skill **必须保留**在结果里，不要因缺「达标」键而过滤掉。

## 执行（用 Bash 工具跑下面这条命令，原样复制）
\`\`\`bash
python3 - <<'PYEOF'
import yaml, glob, json, os
base = os.path.expanduser("${skillBaseFor(dim)}")
out = {"dimension": "${dim}", "skills": []}
for d in sorted(glob.glob(base + "/eval-*")):
    if not os.path.isdir(d): continue
    skill = os.path.basename(d)
    f = d + "/SKILL.md"
    if not os.path.exists(f): continue
    p = open(f).read().split('---', 2)
    if len(p) < 3: continue
    fm = yaml.safe_load(p[1]) or {}
    if not all(k in fm for k in ['title','weight','aggregate']): continue
    w = fm['weight']
    out["skills"].append({
        "skill": skill,
        "title": fm.get('title',''),
        "weight": {"优秀": w.get("优秀",0), "达标": w.get("达标",0), "不达标": w.get("不达标",0)},
        "aggregate": fm.get('aggregate',''),
        "extra": fm.get('extra','') or ''
    })
print(json.dumps(out, ensure_ascii=False))
PYEOF
\`\`\`

## 返回
把脚本 stdout 的 JSON **原样转录**进 schema：dimension 和 skills 数组逐字段对应。不要修改任何数字、不要增删字段、不要肉眼重新解析。若脚本报错（如缺 pyyaml），error 字段说明，skills 返回空数组。`
  return agent(prompt, { label: '发现:' + dim, phase: '评测', schema: DISCOVERY_SCHEMA, model: SUBAGENT_MODEL })
}))

const discoveries = discoveryResults.filter(Boolean)
// 扁平化成 (dimension, skill) 组合
const evalTargets = []
discoveries.forEach(d => {
  (d.skills || []).forEach(s => {
    evalTargets.push({ dimension: d.dimension, skill: s.skill, title: s.title, weight: s.weight, aggregate: s.aggregate, extra: s.extra })
  })
})
log('Phase 2b 完成: 共发现 ' + evalTargets.length + ' 个 eval skill')

if (evalTargets.length === 0) {
  throw new Error('未发现任何 eval skill，检查 dimensions 参数与 ' + dimensions.join(',') + ' 下的 eval-skills/eval-* 目录')
}

// 每个维度的 eval-skills 目录，供合并子代理定位 SKILL.md
const skillDirs = {}
dimensions.forEach(dim => { skillDirs[dim] = skillBaseFor(dim) })

// ---------- Phase 2+3+4+5: 单词全链路合并子代理 ----------
// 原 phase2-annotator / phase3-evaluator / phase4-issue-evidence / phase5-report-renderer
// 四个独立 agent() 调用合并为一次 phase2345-query-pipeline 调用：同一子代理上下文内部顺序完成
// Stage A(本地识别)→B(评测)→C(问题证据)→D(报告)，中间不返回调用方、不切换子代理。
// 所有阶段级契约细节（Phase2 本地识别隔离、八键单图清单、FACT_GATES、共享契约优先、issues/finding 结构、
// 页面框架结论边界、报告渲染分支等）已完整写入 .claude/agents/phase2345-query-pipeline.md，
// 本次调用只注入具体输入值，不在 JS 侧重复拼接任何阶段级 Prompt 文本。
const evalResultFile = artifactRunDir + '/results/评测原始结果_' + query + tagSuffix + '_' + dimSlug + '.json'
const evalAuditFile = artifactRunDir + '/results/评测结果校验_' + query + tagSuffix + '_' + dimSlug + '.json'
const phase2ReviewFile = artifactRunDir + '/results/待回退Phase2复核_' + query + tagSuffix + '_' + dimSlug + '.json'
const issueEvidenceDir = annotatedDir + '/evidence/' + query + tagSuffix

const mergedInputs = {
  query, tag, batchId,
  projectDir,
  screenshots,
  tabs,
  artifactRunDir,
  // Phase2（本地识别）
  annotatedDir,
  imdSkillDir,
  phase2Mode,
  phase2Outputs,
  skipAnnotation,
  // Phase3（评测）
  evalTargets,
  skillDirs,
  granularity,
  evalResultFile,
  evalAuditFile,
  phase2ReviewFile,
  phase2RereviewAuditFile,
  phase2RereviewValidationFile,
  // Phase4（问题证据）
  issueEvidenceSkillDir,
  issueEvidenceDir,
  // Phase5（报告）
  reportSkillDir,
  reportPath,
  reportDir,
  reportImages,
  isBatchGovernanceReport,
  batchArtifactDir,
}

const mergedPrompt = `你正在以 phase2345-query-pipeline agentType 执行当前搜索词的 Phase2→Phase3→Phase4→Phase5 全链路。严格按你的 agent 定义文件执行所有阶段级规则（Phase2 本地识别隔离、八键单图清单、FACT_GATES、共享契约优先读取、issues/finding 结构、页面框架结论边界、报告渲染分支等），本次调用只提供具体输入值，不重复给出规则文本。

## 本次调用输入（JSON，字段名与你的输入契约一一对应）
\`\`\`json
${JSON.stringify(mergedInputs, null, 2)}
\`\`\`
严格按你的输出 schema 一次性回传结果，不要提前中断或跳过阶段。`

const pipelineResult = await agent(mergedPrompt, { label: 'Phase2345全链路:' + query, phase: '评测', schema: PIPELINE_SCHEMA, model: SUBAGENT_MODEL, agentType: 'phase2345-query-pipeline' })
if (!pipelineResult || !pipelineResult.ok) {
  throw new Error('Phase2+3+4+5 单词全链路子代理未通过：blockedAt=' + (pipelineResult && pipelineResult.blockedAt) + ' error=' + (pipelineResult && pipelineResult.error))
}
const stageA = pipelineResult.stageA || {}
const stageB = pipelineResult.stageB || {}
const stageC = pipelineResult.stageC || {}
const stageD = pipelineResult.stageD || {}
const elementListPaths = stageA.elementListPaths || []
const elementAuditPaths = stageA.elementAuditPaths || []
const elementCount = stageA.elementCount || 0
const annotatedPaths = stageA.annotated || []
log('Phase2+3+4+5 完成: elementCount=' + elementCount + ' evalCount=' + (stageB.evalCount || 0) + ' evidenceImages=' + ((stageC.evidenceImages || []).length) + ' report=' + stageD.reportPath)

// ---------- Phase2 manifest 质量侧审计（可选，仅记录 L1/L2/L3 合规率，不阻断） ----------
// phase3-标记权威白名单，仅供本侧审计脚本比对，不再注入合并子代理的 Prompt（Stage A 已在
// agent 定义文件内固化 L1/L2/L3 执行顺序与骨架约束）。
const PHASE3_CARD_TYPES = ['商品卡片', '商家卡片-图文下挂', '商家卡片-文字下挂', '酒店卡片', '度假/酒店套餐卡片', '演出/电影卡片', '主点卡片', '特殊广告卡']
const PHASE3_REGION_NAMES = ['头图区', '标题区', '基础信息区', '标签区', '价格区', '商家区', '下挂区', 'AI推荐理由']
let annotationAudit = null
if (elementListPaths.length === 1 && enableAnnotationAudit) {
  const elementListPath = elementListPaths[0]
  const recognitionAuditFile = phase2Outputs[0].recognitionAudit
  const auditPrompt = `用 Bash 跑下面命令，对元素清单做 phase3-标记自动验收（L1/L2/L3）：
\`\`\`bash
P=$(echo "${elementListPath}")
python3 - "$P" <<'PYEOF'
import json, os, sys

p = sys.argv[1]
ALLOWED_CARD_TYPES = set(${JSON.stringify(PHASE3_CARD_TYPES.concat(['宏观组件']))})
ALLOWED_REGION_NAMES = set(${JSON.stringify(PHASE3_REGION_NAMES)})
ALLOWED_ELEMENT_TYPES = {"文本", "图片", "标签"}
GENERIC_BAD = {
    "原文:商家名称", "原文:评分", "原文:评分 距离 人均", "原文:标签", "原文:基础信息",
    "原文:文字下挂促销", "原文:商品缩略图横滑", "原文:商品图", "原文:价格", "原文:内容未知"
}
CORE_REGIONS = {
    "商品卡片": {"头图区", "标题区", "基础信息区", "价格区", "商家区"},
    "商家卡片-图文下挂": {"头图区", "标题区", "基础信息区", "下挂区"},
    "商家卡片-文字下挂": {"头图区", "标题区", "基础信息区", "下挂区"},
    "酒店卡片": {"头图区", "标题区", "基础信息区"},
    "度假/酒店套餐卡片": {"头图区", "标题区", "基础信息区", "价格区"},
    "演出/电影卡片": {"标题区", "基础信息区", "价格区"},
    "主点卡片": {"标题区", "基础信息区"},
    "特殊广告卡": {"标题区"},
}

def valid_coord(v):
    return isinstance(v, list) and len(v) == 4 and all(isinstance(x, (int, float)) for x in v)

if not os.path.exists(p):
    print("AUDIT_OK=0")
    print("AUDIT_ERR=file_not_found")
    sys.exit()

try:
    d = json.load(open(p))
    cards = d.get('cards', []) if isinstance(d, dict) else []

    total_cards = len(cards)
    total_regions = 0
    total_elements = 0
    non_excluded_elements = 0

    l1_valid = 0
    l2_name_valid = 0
    l3_type_valid = 0
    l3_coord_valid = 0
    l3_exclude_valid = 0
    l3_text_valid = 0

    seen_types = set()
    missing_core = []

    for c in cards:
        if not isinstance(c, dict):
            continue
        ctype = str(c.get('卡片类型', '')).strip()
        if ctype in ALLOWED_CARD_TYPES:
            l1_valid += 1
        seen_types.add(ctype)

        if ctype == '宏观组件':
            continue

        regions = c.get('regions', [])
        if not isinstance(regions, list):
            regions = []
        names = set()
        for r in regions:
            total_regions += 1
            if not isinstance(r, dict):
                continue
            rn = str(r.get('name', '')).strip()
            names.add(rn)
            if rn in ALLOWED_REGION_NAMES:
                l2_name_valid += 1

            elements = r.get('elements', [])
            if not isinstance(elements, list):
                elements = []
            for e in elements:
                total_elements += 1
                if not isinstance(e, dict):
                    continue
                et = str(e.get('元素类型', '')).strip()
                if et in ALLOWED_ELEMENT_TYPES:
                    l3_type_valid += 1
                if valid_coord(e.get('坐标')):
                    l3_coord_valid += 1

                ex = e.get('isExcluded')
                reason = e.get('excludeReason')
                if isinstance(ex, bool) and isinstance(reason, str) and ((ex and reason.strip()) or (not ex)):
                    l3_exclude_valid += 1
                if isinstance(ex, bool) and not ex:
                    non_excluded_elements += 1
                    txt = str(e.get('内容简述', '')).strip()
                    if txt.startswith('原文:') and txt not in GENERIC_BAD:
                        l3_text_valid += 1

        core = CORE_REGIONS.get(ctype, set())
        if core:
            miss = sorted(list(core - names))
            if miss:
                missing_core.append(str(c.get('cardId', 'unknown')) + ':' + ','.join(miss))

    def rate(ok, total):
        return 1.0 if total == 0 else float(ok) / float(total)

    l1_rate = rate(l1_valid, total_cards)
    l2_rate = rate(l2_name_valid, total_regions)
    l3_type_rate = rate(l3_type_valid, total_elements)
    l3_coord_rate = rate(l3_coord_valid, total_elements)
    l3_exclude_rate = rate(l3_exclude_valid, total_elements)
    l3_text_rate = rate(l3_text_valid, non_excluded_elements)
    l3_rate = min(l3_type_rate, l3_coord_rate, l3_exclude_rate, l3_text_rate)

    print("AUDIT_OK=1")
    print("TOTAL_CARDS=" + str(total_cards))
    print("TOTAL_REGIONS=" + str(total_regions))
    print("TOTAL_ELEMENTS=" + str(total_elements))
    print("NON_EXCLUDED_ELEMENTS=" + str(non_excluded_elements))
    print("L1_CARD_TYPE_RATE=" + format(l1_rate, '.4f'))
    print("L2_REGION_NAME_RATE=" + format(l2_rate, '.4f'))
    print("L3_TYPE_RATE=" + format(l3_type_rate, '.4f'))
    print("L3_COORD_RATE=" + format(l3_coord_rate, '.4f'))
    print("L3_EXCLUDE_RATE=" + format(l3_exclude_rate, '.4f'))
    print("L3_TEXT_RATE=" + format(l3_text_rate, '.4f'))
    print("L3_OVERALL_RATE=" + format(l3_rate, '.4f'))
    print("USED_L1_TYPES=" + ('|'.join(sorted([x for x in seen_types if x])) if seen_types else 'NONE'))
    print("MISSING_CORE_REGIONS=" + (';'.join(missing_core) if missing_core else 'NONE'))
except Exception as ex:
    print("AUDIT_OK=0")
    print("AUDIT_ERR=" + str(ex)[:120])
PYEOF
\`\`\`
把 stdout 原样放进 schema 返回。`

  const auditResult = await agent(auditPrompt, { label: 'Manifest验收', phase: '评测', schema: ANNOTATE_AUDIT_SCHEMA, model: SUBAGENT_MODEL })
  const auditOut = (auditResult && auditResult.stdout) || ''
  const pickNum = (k) => {
    const mm = auditOut.match(new RegExp(k + '=(\\d+(?:\\.\\d+)?)'))
    return mm ? Number(mm[1]) : null
  }
  const pickStr = (k) => {
    const mm = auditOut.match(new RegExp(k + '=([^\n]*)'))
    return mm ? mm[1].trim() : ''
  }

  annotationAudit = {
    ok: pickNum('AUDIT_OK') === 1,
    recognitionAuditPath: recognitionAuditFile,
    totalCards: pickNum('TOTAL_CARDS'),
    totalRegions: pickNum('TOTAL_REGIONS'),
    totalElements: pickNum('TOTAL_ELEMENTS'),
    nonExcludedElements: pickNum('NON_EXCLUDED_ELEMENTS'),
    l1CardTypeRate: pickNum('L1_CARD_TYPE_RATE'),
    l2RegionNameRate: pickNum('L2_REGION_NAME_RATE'),
    l3TypeRate: pickNum('L3_TYPE_RATE'),
    l3CoordRate: pickNum('L3_COORD_RATE'),
    l3ExcludeRate: pickNum('L3_EXCLUDE_RATE'),
    l3TextRate: pickNum('L3_TEXT_RATE'),
    l3OverallRate: pickNum('L3_OVERALL_RATE'),
    usedL1Types: pickStr('USED_L1_TYPES'),
    missingCoreRegions: pickStr('MISSING_CORE_REGIONS'),
    error: pickStr('AUDIT_ERR'),
    raw: auditOut,
  }

  const l1 = annotationAudit.l1CardTypeRate == null ? 'NA' : Math.round(annotationAudit.l1CardTypeRate * 1000) / 10 + '%'
  const l2 = annotationAudit.l2RegionNameRate == null ? 'NA' : Math.round(annotationAudit.l2RegionNameRate * 1000) / 10 + '%'
  const l3 = annotationAudit.l3OverallRate == null ? 'NA' : Math.round(annotationAudit.l3OverallRate * 1000) / 10 + '%'
  log('Manifest质量侧审计: L1=' + l1 + ' L2=' + l2 + ' L3=' + l3 + (annotationAudit.ok ? '' : ' (audit failed)'))
}

log('全部完成: 报告已生成 → ' + stageD.reportPath)
return {
  query: query,
  dimensions: dimensions,
  screenshotsCount: screenshots.length,
  annotatedCount: annotatedPaths.length,
  evalSkillsCount: stageB.evalCount || 0,
  annotationAudit: annotationAudit,
  report: stageD,
  deterministicAudits: {
    manifests: elementAuditPaths,
    recognition: phase2Outputs.map(item => item.recognitionAudit),
    evaluations: elementListPaths.length ? evalAuditFile : '',
  },
}
