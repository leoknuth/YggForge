/**
 * YggForge 与同类开源项目对比（Cursor Canvas）。
 * 正文结论见同目录上级：docs/assessments/oss-comparison.md
 * 打开方式见：docs/assessments/canvases/README.md
 */
import {
  BarChart,
  Callout,
  Card,
  CardBody,
  CardHeader,
  Divider,
  Grid,
  H1,
  H2,
  H3,
  Pill,
  Row,
  Spacer,
  Stack,
  Stat,
  Table,
  Text,
} from "cursor/canvas";

type Peer = {
  name: string;
  kind: string;
  url: string;
  stars: string;
  oneLiner: string;
  pros: string;
  cons: string;
  scores: {
    gitTruth: number;
    multiAgent: number;
    layerPromote: number;
    retrieval: number;
    autoCapture: number;
    opsEase: number;
    maturity: number;
    localControl: number;
  };
  fitEngKnowledge: number;
  fitSessionMemory: number;
};

const PEERS: Peer[] = [
  {
    name: "YggForge",
    kind: "工程知识锻造仓",
    url: "本地仓库",
    stars: "私有/团队",
    oneLiner: "Git 真源 + 人类式 tag 联想 + remember→promote 演化；rules / templates·skills / lessons·sources 多层自迭代",
    pros: "人类可审、可版本化；投影清晰；晋升有门禁；人类式联想检索；可在逻辑/技能/知识多层持续自迭代",
    cons: "社区小；会话自动捕获弱于专用记忆层；向量/hybrid 尚未落地；生态工具链仍薄",
    scores: {
      gitTruth: 9,
      multiAgent: 9,
      layerPromote: 9,
      retrieval: 7,
      autoCapture: 3,
      opsEase: 7,
      maturity: 3,
      localControl: 9,
    },
    fitEngKnowledge: 90,
    fitSessionMemory: 48,
  },
  {
    name: "Agentic Workspace Core",
    kind: "仓库原生 agent 基础设施",
    url: "github.com/Daaaaave/agentic-workspace-core",
    stars: "小众",
    oneLiner: "向业务仓安装 AGENTS.md、skills、docs 知识与 llms.txt 导航，强调可审查、可 git",
    pros: "与编码 Agent 同仓；迁移/归档旧规则有流程；偏「装进业务仓」而非另起知识仓",
    cons: "锻造成型（ingest/distill/promote）弱于 YggForge；检索偏导航生成",
    scores: {
      gitTruth: 9,
      multiAgent: 7,
      layerPromote: 6,
      retrieval: 5,
      autoCapture: 2,
      opsEase: 7,
      maturity: 4,
      localControl: 9,
    },
    fitEngKnowledge: 74,
    fitSessionMemory: 35,
  },
  {
    name: "agentmemory",
    kind: "MCP 持久记忆（LLM Wiki 实现）",
    url: "github.com/rohitg00/agentmemory",
    stars: "~2.5k",
    oneLiner: "跨 Cursor/Claude/Codex 等的持久记忆：自动捕获、分层巩固、混合检索、知识图",
    pros: "会话记忆强；混合检索成熟；多客户端 MCP 一键接入；社区活跃",
    cons: "真源更偏「记忆库」而非工程制度仓；人类直接审稿路径弱于 Markdown 分层仓",
    scores: {
      gitTruth: 5,
      multiAgent: 9,
      layerPromote: 5,
      retrieval: 9,
      autoCapture: 9,
      opsEase: 6,
      maturity: 7,
      localControl: 7,
    },
    fitEngKnowledge: 62,
    fitSessionMemory: 90,
  },
  {
    name: "agent-knowledge",
    kind: "MCP 知识编译层",
    url: "github.com/yucx-go/agent-knowledge",
    stars: "较小",
    oneLiner: "对话/文档编译为 claim+证据；BM25+KG+RRF；无向量依赖的 MCP 长期记忆",
    pros: "检索评测叙事清晰；纯 Python 本地优先；矛盾检测等「编译知识」能力",
    cons: "工程规范分层/多端投影弱；更偏记忆编译而非团队制度仓库",
    scores: {
      gitTruth: 6,
      multiAgent: 7,
      layerPromote: 6,
      retrieval: 8,
      autoCapture: 7,
      opsEase: 6,
      maturity: 3,
      localControl: 8,
    },
    fitEngKnowledge: 64,
    fitSessionMemory: 78,
  },
  {
    name: "Mem0",
    kind: "通用 Agent 记忆层 API",
    url: "github.com/mem0ai/mem0",
    stars: "~60k",
    oneLiner: "抽事实、去重、持久化的 drop-in memory API；OSS + 托管云",
    pros: "接入最快；生态最大；适合个性化助手与产品 Agent",
    cons: "不是工程知识真源；人类用 IDE 维护规范体验弱；托管路径有厂商耦合",
    scores: {
      gitTruth: 3,
      multiAgent: 6,
      layerPromote: 3,
      retrieval: 8,
      autoCapture: 8,
      opsEase: 8,
      maturity: 9,
      localControl: 5,
    },
    fitEngKnowledge: 42,
    fitSessionMemory: 84,
  },
  {
    name: "Graphiti (Zep)",
    kind: "时序知识图引擎",
    url: "github.com/getzep/Graphiti",
    stars: "~29k",
    oneLiner: "带有效期的时序图谱；擅长「何时为真」类检索；Zep 为其托管壳",
    pros: "时序事实一流；关系推理强；开源引擎可自建",
    cons: "运维重（图库/抽取成本）；不解决多 Agent 规则投影与错题晋升",
    scores: {
      gitTruth: 3,
      multiAgent: 4,
      layerPromote: 2,
      retrieval: 9,
      autoCapture: 6,
      opsEase: 4,
      maturity: 8,
      localControl: 6,
    },
    fitEngKnowledge: 38,
    fitSessionMemory: 80,
  },
  {
    name: "Letta",
    kind: "带自管记忆的 Agent 运行时",
    url: "github.com/letta-ai/letta",
    stars: "~20k+",
    oneLiner: "MemGPT 谱系：Agent 自己管理 core/archival memory，适合长程自治",
    pros: "长程状态强；记忆由 Agent 工具自管理；评测叙事亮眼",
    cons: "是运行时而非知识仓；团队制度/多工具投影不是其主战场",
    scores: {
      gitTruth: 3,
      multiAgent: 3,
      layerPromote: 3,
      retrieval: 7,
      autoCapture: 7,
      opsEase: 4,
      maturity: 8,
      localControl: 6,
    },
    fitEngKnowledge: 34,
    fitSessionMemory: 82,
  },
  {
    name: "Karpathy LLM Wiki",
    kind: "模式（非产品）",
    url: "gist / 社区复刻",
    stars: "模式级",
    oneLiner: "raw → LLM 编译 wiki → schema；ingest/query/lint，强调编译知识优于裸 RAG",
    pros: "思想与 YggForge「锻造」高度同向；实现可极简 Markdown",
    cons: "本身不是可部署产品；自动 lint/编译需自建或借 agentmemory 等",
    scores: {
      gitTruth: 8,
      multiAgent: 4,
      layerPromote: 7,
      retrieval: 5,
      autoCapture: 2,
      opsEase: 5,
      maturity: 6,
      localControl: 9,
    },
    fitEngKnowledge: 70,
    fitSessionMemory: 40,
  },
  {
    name: "Obsidian",
    kind: "PKM 壳（非记忆引擎）",
    url: "obsidian.md",
    stars: "主流 PKM",
    oneLiner: "本地 Markdown vault + 双链图谱；常作 LLM Wiki / Agent 的人机界面",
    pros: "人类编辑体验顶尖；双链可视化；数据本地；可直接打开仓库目录",
    cons: "不是记忆引擎或晋升系统；多 Agent 投影与门禁需自建",
    scores: {
      gitTruth: 9,
      multiAgent: 5,
      layerPromote: 5,
      retrieval: 4,
      autoCapture: 2,
      opsEase: 8,
      maturity: 9,
      localControl: 9,
    },
    fitEngKnowledge: 72,
    fitSessionMemory: 30,
  },
  {
    name: "Hindsight",
    kind: "会学习的 Agent 记忆",
    url: "github.com/vectorize-io/hindsight",
    stars: "~18k",
    oneLiner: "retain / recall / reflect；TEMPR 多策略检索；观察巩固与 disposition",
    pros: "自动巩固与 reflect 强；四路融合检索；MCP/SDK/wrapper 接入多",
    cons: "非工程制度真源；需部署服务；不解决多工具规范投影",
    scores: {
      gitTruth: 3,
      multiAgent: 6,
      layerPromote: 4,
      retrieval: 9,
      autoCapture: 8,
      opsEase: 6,
      maturity: 8,
      localControl: 7,
    },
    fitEngKnowledge: 40,
    fitSessionMemory: 88,
  },
  {
    name: "GraphRAG",
    kind: "语料级 Graph RAG",
    url: "github.com/microsoft/graphrag",
    stars: "~30k",
    oneLiner: "实体抽取→社区层级→全局/局部问答；面向文档库而非制度仓",
    pros: "全局主题与多跳问答强于朴素向量 RAG；研究与开源叙事成熟",
    cons: "全量索引贵；不解多 Agent 投影与晋升；图是语料结构非团队规范",
    scores: {
      gitTruth: 4,
      multiAgent: 2,
      layerPromote: 2,
      retrieval: 9,
      autoCapture: 2,
      opsEase: 3,
      maturity: 9,
      localControl: 6,
    },
    fitEngKnowledge: 28,
    fitSessionMemory: 45,
  },
  {
    name: "Memary",
    kind: "图+记忆流实验层",
    url: "github.com/kingjulio8238/memary",
    stars: "~2.6k",
    oneLiner: "Neo4j KG + Memory Stream / Entity Knowledge Store；偏研究原型",
    pros: "图检索与实体频度/近因建模思路清晰；适合学架构",
    cons: "维护偏实验；运维绑 Neo4j；不宜作生产制度真源",
    scores: {
      gitTruth: 3,
      multiAgent: 3,
      layerPromote: 3,
      retrieval: 7,
      autoCapture: 6,
      opsEase: 3,
      maturity: 5,
      localControl: 6,
    },
    fitEngKnowledge: 36,
    fitSessionMemory: 70,
  },
  {
    name: "Cognee",
    kind: "图+向量记忆流水线",
    url: "github.com/topoteretes/cognee",
    stars: "活跃 OSS",
    oneLiner: "ECL（Extract–Cognify–Load）；多种检索模式；本地/云可选",
    pros: "流水线完整；图+向量混合；可自托管",
    cons: "仍是记忆层而非规范投影仓；抽取与运维成本高于纯 Markdown 仓",
    scores: {
      gitTruth: 4,
      multiAgent: 5,
      layerPromote: 4,
      retrieval: 9,
      autoCapture: 7,
      opsEase: 5,
      maturity: 7,
      localControl: 7,
    },
    fitEngKnowledge: 44,
    fitSessionMemory: 82,
  },
];

const DIM_LABELS: { key: keyof Peer["scores"]; label: string }[] = [
  { key: "gitTruth", label: "Git/人类真源" },
  { key: "multiAgent", label: "多 Agent 投影" },
  { key: "layerPromote", label: "分层与晋升" },
  { key: "retrieval", label: "检索能力" },
  { key: "autoCapture", label: "自动捕获" },
  { key: "opsEase", label: "运维省心" },
  { key: "maturity", label: "生态成熟度" },
  { key: "localControl", label: "本地可控" },
];

function avgScore(p: Peer): number {
  const vals = Object.values(p.scores);
  return Math.round((vals.reduce((a, b) => a + b, 0) / vals.length) * 10) / 10;
}

export default function YggForgeComparisonCanvas() {
  const engSorted = [...PEERS].sort((a, b) => b.fitEngKnowledge - a.fitEngKnowledge);

  return (
    <Stack gap={24} style={{ padding: 24, maxWidth: 1100 }}>
      <Stack gap={8}>
        <H1>YggForge 与同类开源项目对比</H1>
        <Text tone="secondary">
          场景拆成两条轴：工程知识真源（团队规范/错题/决策）vs 会话持久记忆（跨对话记住事实）。
          得分来自公开资料与能力对齐的主观评估（1–10 / 0–100），非基准跑分。资料截止约 2026-07。
        </Text>
        <Row gap={8} style={{ flexWrap: "wrap" }}>
          <Pill tone="info">YggForge：联想 + 自迭代 + 投影</Pill>
          <Pill>竞品强项：自动记忆+混合检索</Pill>
          <Pill tone="neutral">可互补，不必二选一</Pill>
        </Row>
      </Stack>

      <Grid columns={4} gap={12}>
        <Stat value="90" label="YggForge · 工程知识拟合" tone="info" />
        <Stat value="48" label="YggForge · 会话记忆拟合" />
        <Stat value="90" label="最高会话记忆分 (agentmemory)" />
        <Stat value="14" label="对比项目数" />
      </Grid>

      <Callout tone="info" title="怎么读这份对比">
        YggForge 更接近「可版本化、可联想、可自我迭代的工程知识操作系统」：tag 图联想记忆，
        并在 rules / templates·skills / lessons·sources 等层持续演化（强规范仍经审核）。
        Mem0 / Hindsight / Graphiti / Letta 更接近「Agent 运行时记忆层」；
        GraphRAG 是语料问答；Obsidian 是 PKM 壳。可互补，不必二选一。
      </Callout>

      <H2>场景拟合总分（0–100）</H2>
      <Text tone="secondary" size="small">
        Source: 主观评分 · 工程知识轴加权偏 Git 真源/分层晋升/多端投影；会话记忆轴加权偏自动捕获与检索
      </Text>
      <BarChart
        categories={engSorted.map((p) => p.name)}
        series={[
          {
            name: "工程知识真源拟合",
            data: engSorted.map((p) => p.fitEngKnowledge),
            tone: "info",
          },
          {
            name: "会话持久记忆拟合",
            data: engSorted.map((p) => {
              const peer = PEERS.find((x) => x.name === p.name)!;
              return peer.fitSessionMemory;
            }),
            tone: "neutral",
          },
        ]}
        height={280}
      />

      <H2>能力雷达分（八维均值）</H2>
      <Table
        headers={[
          "项目",
          "类型",
          "均值",
          ...DIM_LABELS.map((d) => d.label),
          "工程拟合",
          "记忆拟合",
        ]}
        rows={PEERS.map((p) => [
          p.name,
          p.kind,
          String(avgScore(p)),
          ...DIM_LABELS.map((d) => String(p.scores[d.key])),
          String(p.fitEngKnowledge),
          String(p.fitSessionMemory),
        ])}
        rowTone={PEERS.map((p) => (p.name === "YggForge" ? "info" : undefined))}
      />

      <H2>逐项速览</H2>
      <Stack gap={12}>
        {PEERS.map((p) => (
          <Card>
            <CardHeader
              trailing={
                <Row gap={6}>
                  <Pill tone={p.name === "YggForge" ? "info" : "neutral"} size="sm">
                    工程 {p.fitEngKnowledge}
                  </Pill>
                  <Pill size="sm">记忆 {p.fitSessionMemory}</Pill>
                </Row>
              }
            >
              {p.name}
            </CardHeader>
            <CardBody>
              <Stack gap={8}>
                <Text tone="secondary" size="small">
                  {p.kind} · {p.stars} · {p.url}
                </Text>
                <Text>{p.oneLiner}</Text>
                <Grid columns={2} gap={12}>
                  <Stack gap={4}>
                    <H3>优点</H3>
                    <Text size="small">{p.pros}</Text>
                  </Stack>
                  <Stack gap={4}>
                    <H3>缺点</H3>
                    <Text size="small">{p.cons}</Text>
                  </Stack>
                </Grid>
              </Stack>
            </CardBody>
          </Card>
        ))}
      </Stack>

      <Divider />

      <H2>选型建议</H2>
      <Grid columns={2} gap={12}>
        <Card>
          <CardHeader>优先选 YggForge 当</CardHeader>
          <CardBody>
            <Stack gap={6}>
              <Text size="small">要把规范/模板/错题/决策当成 Git 真源长期维护</Text>
              <Text size="small">需要同时投影到 Cursor / Codex / OpenCode</Text>
              <Text size="small">需要人类式概念联想（associate），而不只靠关键词</Text>
              <Text size="small">希望系统在协作中持续进化 rules / skills(SOP) / lessons·sources</Text>
              <Text size="small">强调「草稿→审核→晋升」，禁止 Agent 静默改强规则</Text>
              <Text size="small">内网/密钥边界清晰，本地可控优先于托管记忆云</Text>
            </Stack>
          </CardBody>
        </Card>
        <Card>
          <CardHeader>优先叠加/改选竞品当</CardHeader>
          <CardBody>
            <Stack gap={6}>
              <Text size="small">要跨会话自动记住对话事实 → agentmemory / Mem0</Text>
              <Text size="small">要「事实何时为真」时序推理 → Graphiti/Zep</Text>
              <Text size="small">要长程自治 Agent 自管记忆 → Letta</Text>
              <Text size="small">只想给业务仓装 AGENTS.md+skills → Agentic Workspace Core</Text>
            </Stack>
          </CardBody>
        </Card>
      </Grid>

      <Spacer height={8} />
      <Text tone="tertiary" size="small">
        评分说明：八维各 1–10；工程/记忆拟合为场景加权后的 0–100。星标与生态数据随时间变化，以各仓库 README
        与公开评测文章为准。YggForge 为你正在使用的仓库能力快照，非公开发布榜单。
      </Text>
      <Text tone="tertiary" size="small">
        参考：fountaincity / particula / AgentsCamp 等 2026 Agent Memory 对比文；GitHub README of
        mem0、Graphiti、agentmemory、agentic-workspace-core、agent-knowledge。
      </Text>
    </Stack>
  );
}
