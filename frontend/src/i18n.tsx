import { createContext, useContext, useState, ReactNode, useEffect } from 'react'

export type Lang = 'zh' | 'en'

const dict = {
  zh: {
    cancel: '取消', confirm: '确认', refresh: '刷新', close: '关闭',
    bioagent: 'BioAgent', subtitle: '生信分析工作台', project: '项目', stage: '阶段',
    agent: 'Agent', env: '计算环境', envNone: '未指定', local: '本地', remote: '远程',
    noLogin: '单机免登录', settings: '设置', logout: '退出', search: '搜索',
    projects: '项目', new: '新建', manage: '管理', selectedCount: '已选',
    delete: '删除', rename: '重命名', reposition: '重定位', localProjects: '本地项目',
    remoteProjects: '服务器端项目', createProject: '新建项目', projectName: '项目名称',
    projectCategory: '项目类别', localProject: '本地项目', remoteProject: '服务器端项目',
    workdir: '工作区文件夹', browse: '浏览', server: '服务器', addServer: '添加新服务器',
    serverWorkdir: '工作区目录名（服务器上）', create: '创建', noProjects: '暂无项目',
    datasets: '数据集', events: '事件', type: '类型',
    conversation: '对话', inputPlaceholder: '描述分析需求…（QC / 聚类 / 注释 / UMAP / 差异表达 / 继续）',
    send: '发送', fullAnalysis: '完整分析', dataCheck: '数据检查', clustering: '聚类',
    annotation: '注释', deAnalysis: '差异表达', continue: '继续', analyzing: '分析执行中，事件进度见历史面板…',
    noMessages: '与 BioAgent 对话，用自然语言描述分析需求，例如「聚类，分辨率 1.0」。',
    resultTabs: '历史 DAG', artifacts: '产物', datasetsTab: '数据集',
    noProject: '选择一个项目查看分析历史。', noEvent: '还没有分析事件。在对话中发出第一个分析请求，例如「聚类，分辨率 0.5」。',
    dagLegend: '依赖边由数据集版本链推导，重跑以 re_run 边标记（fork）。点击节点查看详情。',
    compareEvents: '对比事件', compare: '对比', compareSelec: '对比事件',
    generateReport: '生成分析报告', all: '全部',
    username: '用户名', password: '密码', login: '登录', register: '注册',
    loginTitle: '生信分析 Agent 工作平台', firstAdmin: '首个注册的用户将获得管理员权限',
    workMode: '工作模式（执行器）', agentMode: 'Agent 模式', llmApiKey: 'LLM API Key',
    computeEnv: '计算环境', capabilityResolve: '能力解析（Tool → Capability）', api: 'API',
    system: '系统', standaloneMode: '单机模式（免登录，个人本机使用）',
    deleteFilesNote: '同时删除 log 和已生成的图片/产物文件（不可恢复）', confirmDelete: '确认删除',
    browseHint: '可浏览选择已存在的目录，或输入路径后自动创建。', selectServer: '选择已链接的服务器',
    sshServer: 'SSH 服务器', serverName: '服务器名（如 Lab HPC）', serverHost: '服务器地址',
    port: '端口', account: '账号', add: '添加',
    rstudio: 'RStudio 接手', rstudioHandoff: '生成 RStudio 交接包', rstudioDownload: '下载待跑脚本(.R/zip)',
    rstudioAnalyzing: '用 RStudio 手动分析此步骤', rstudioImport: '导入 RStudio 结果',
    rstudioImportHint: '在 RStudio 中运行交接脚本并把产物写入 rstudio_output/ 后,点击导入。',
    rstudioHandoffDone: '交接包已生成。可在 RStudio 打开 analysis.R 手动运行,或下载 zip 到本地。',
    rstudioImported: '已导入 RStudio 结果,产物已注册为数据集/产物并延续分析链路。',
    rstudioNoOutput: '未在输出目录找到产物文件,请先在 RStudio 中运行脚本生成产物。',
    rstudioROnly: '该步骤不是 R 类分析,暂不支持 RStudio 手动接手。',
    rstudioPrior: '前序结果', rstudioOpenZip: '下载交接包', rstudioOutputDir: '产物输出目录',
  },
  en: {
    cancel: 'Cancel', confirm: 'Confirm', refresh: 'Refresh', close: 'Close',
    bioagent: 'BioAgent', subtitle: 'Bioinformatics Analysis Workbench', project: 'Project', stage: 'Stage',
    agent: 'Agent', env: 'Compute Env', envNone: 'None', local: 'Local', remote: 'Remote',
    noLogin: 'Standalone (no login)', settings: 'Settings', logout: 'Logout', search: 'Search',
    projects: 'Projects', new: 'New', manage: 'Manage', selectedCount: 'Selected',
    delete: 'Delete', rename: 'Rename', reposition: 'Reposition', localProjects: 'Local Projects',
    remoteProjects: 'Server Projects', createProject: 'New Project', projectName: 'Project Name',
    projectCategory: 'Project Type', localProject: 'Local Project', remoteProject: 'Server Project',
    workdir: 'Workspace Folder', browse: 'Browse', server: 'Server', addServer: 'Add Server',
    serverWorkdir: 'Workspace dir (on server)', create: 'Create', noProjects: 'No projects yet',
    datasets: 'Datasets', events: 'Events', type: 'Type',
    conversation: 'Conversation', inputPlaceholder: 'Describe an analysis need… (QC / Cluster / Annotate / UMAP / DE / Continue)',
    send: 'Send', fullAnalysis: 'Full Analysis', dataCheck: 'Data Check', clustering: 'Cluster',
    annotation: 'Annotate', deAnalysis: 'Differential Expression', continue: 'Continue', analyzing: 'Analyzing… see event progress in history panel',
    noMessages: 'Talk to BioAgent in natural language, e.g. "cluster with resolution 1.0".',
    resultTabs: 'History DAG', artifacts: 'Artifacts', datasetsTab: 'Datasets',
    noProject: 'Select a project to view analysis history.',
    noEvent: 'No analysis events yet. Send a request in the chat, e.g. "cluster with resolution 0.5".',
    dagLegend: 'Dependency edges derive from the dataset version chain; reruns are marked as re_run (fork). Click a node for details.',
    compareEvents: 'Compare Events', compare: 'Compare', compareSelec: 'Compare events',
    generateReport: 'Generate Report', all: 'All',
    username: 'Username', password: 'Password', login: 'Login', register: 'Register',
    loginTitle: 'Bioinformatics Analysis Agent Platform', firstAdmin: 'The first registered user becomes admin',
    workMode: 'Execution Mode', agentMode: 'Agent Mode', llmApiKey: 'LLM API Key',
    computeEnv: 'Compute Environments', capabilityResolve: 'Capability Resolver (Tool → Capability)', api: 'API',
    system: 'System', standaloneMode: 'Standalone mode (no login, for personal use)',
    deleteFilesNote: 'Also delete logs and generated images/artifacts (irreversible)', confirmDelete: 'Confirm Delete',
    browseHint: 'Browse an existing directory, or enter a path to auto-create.', selectServer: 'Select a linked server',
    sshServer: 'SSH Server', serverName: 'Server name (e.g. Lab HPC)', serverHost: 'Server address',
    port: 'Port', account: 'Account', add: 'Add',
    rstudio: 'RStudio Handoff', rstudioHandoff: 'Generate RStudio handoff package', rstudioDownload: 'Download script (.R/zip)',
    rstudioAnalyzing: 'Analyze this step manually in RStudio', rstudioImport: 'Import RStudio results',
    rstudioImportHint: 'Run the handoff script in RStudio and write outputs into rstudio_output/, then click Import.',
    rstudioHandoffDone: 'Handoff package ready. Open analysis.R in RStudio to run manually, or download the zip locally.',
    rstudioImported: 'RStudio results imported; outputs registered as datasets/artifacts and linked into the pipeline.',
    rstudioNoOutput: 'No artifact files found in the output directory. Run the script in RStudio first.',
    rstudioROnly: 'This step is not an R-based analysis, so RStudio handoff is not available.',
    rstudioPrior: 'Prior results', rstudioOpenZip: 'Download handoff package', rstudioOutputDir: 'Output directory',
  },
}

const Ctx = createContext<{ lang: Lang; setLang: (l: Lang) => void; t: (k: string) => string }>({
  lang: 'zh', setLang: () => {}, t: (k) => k,
})

export function LangProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(() => (localStorage.getItem('bioagent_lang') as Lang) || 'zh')
  useEffect(() => { document.documentElement.lang = lang }, [lang])
  const setLang = (l: Lang) => { setLangState(l); localStorage.setItem('bioagent_lang', l) }
  const t = (k: string) => (dict[lang] as Record<string, string>)[k] ?? (dict.zh as Record<string, string>)[k] ?? k
  return <Ctx.Provider value={{ lang, setLang, t }}>{children}</Ctx.Provider>
}

export const useI18n = () => useContext(Ctx)
