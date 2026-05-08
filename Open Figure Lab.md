可以。下面我按真实产品方案来写，不是泛泛聊概念。

# 科研图表版 Open Design：MVP 产品方案 v1

我建议这个产品暂定名叫：

## **Open Figure Lab**

**一个本地优先、agent 驱动、面向出版级科研图表的工作台。**

它借鉴 Open Design 的核心机制：本地运行、接入已有 coding agent、用 skills 驱动产物生成、预览、导出、迭代。Open Design 自己的描述里就强调它不是再造 agent，而是把本机最强的 coding agents 接入一个 skill-driven design workflow；并且支持 OpenCode、Codex、Claude Code、Cursor 等 agent。

但我们要把设计目标从“网页/产品原型”换成：

> **论文图表、科研图形、多面板 figure、地图组合图、概念框架图、补充图、期刊投稿图。**

---

## 1. 产品定位

### 不是

* 不是 Origin 替代品
* 不是 Figma 替代品
* 不是 AI 图片生成器
* 不是简单 matplotlib prompt 工具

### 而是

## **科研图表的 agentic production system**

它的核心价值是：

1. **用自然语言生成图**
2. **用自然语言修改图**
3. **保证数据不被乱改**
4. **保证多张图风格统一**
5. **输出可编辑、可复现、可投稿的图表资产**

这比“让 AI 画一张漂亮图”重要得多。

---

## 2. 为什么这个方向成立

现在已经有几个生态趋势可以支撑这个产品。

第一，`nature-skills` 这类项目已经把 Nature 风格科研表达做成 skill 化集合，覆盖 scientific figures、论文润色、data availability、paper-to-presentation 等；其中 `nature-figure` 明确面向多面板 matplotlib、Nature 风格、语义配色和可编辑 SVG 输出。

第二，现有绘图生态已经出现“科研图表专用小工具”的趋势。例如 `figquilt` 是一个用 YAML/JSON layout 文件把 PDF/SVG/PNG 组合成 publication-ready figure 的语言无关 CLI；这说明“结构化拼图 + 跨语言图层组合”是一个很好的方向。([PyPI][1])

第三，`Pylustrator` 这类工具已经指出科研图表的一大痛点：很多人先用 matplotlib 生成基础图，再用矢量软件手工排版，但这会破坏可复现性；它的思路是用 GUI 交互调整 figure，同时把所有修改追踪并回写成代码。这个思想对我们非常关键：**交互修改必须可代码化、可追踪、可复现。** ([arXiv][2])

第四，期刊规范本身也支持这个产品。Nature 的图形指南明确建议 Python 输出 PDF 时使用 `Matplotlib.rcParams['pdf.fonttype']=42`，避免文字被转成轮廓，并要求线、箭头、比例尺、文字等尽量作为可编辑矢量元素导出。([自然研究图示指南][3]) Nature 也说明初投稿可接受 `.ai`, `.eps`, `.pdf`, `.ps`, `.svg` 等 fully editable vector-based art，字体一般在目标尺寸下 5–7 pt。([Nature][4]) Elsevier 也把 EPS/PDF/TIFF/JPEG 作为主要图形格式，其中 EPS 是矢量图、图表、技术绘图和注释图的推荐格式。([www.elsevier.com][5])

所以这个产品不是空想，而是刚好卡在一个真实缺口：

> **科研人员会写代码，但做不出出版级图；设计软件能精修，但不够可复现；AI 能出草图，但不可信、不稳定。**

Open Figure Lab 就是补中间这一层。

---

# 3. MVP 的一句话定义

## **输入数据和绘图意图，agent 根据科研图表 skills 生成、检查、修改并导出出版级多面板 figure。**

第一版不要做太大。
只做一个核心场景：

> **Nature / Science 风格的多面板科研图表生成与迭代。**

---

# 4. MVP 用户画像

第一批用户就是我们这种人：

### A. 会 Python/R，但不擅长设计的科研人员

痛点：

* 图能画出来，但不好看
* 多图风格不统一
* 改一个 panel 要重写很多代码
* SVG/PDF 导出经常字体、线宽、图例出问题

### B. 有大量数据分析结果，需要快速变成论文图的人

痛点：

* 结果已经有 CSV
* 但是不知道该用什么图讲故事
* 需要多次换版式、换颜色、换 panel 结构

### C. GIS/RS/生态/生物/医学等多面板图重灾区

痛点：

* 地图 + 统计图 + 机制图 + 图例组合很麻烦
* ArcGIS/QGIS 出地图，Python 出统计图，AI/Figma/Illustrator 拼版
* 每一步都割裂

---

# 5. 核心差异化

这个产品最重要的差异化不是“生成图”，而是下面五个能力。

## 5.1 数据可信

所有图必须从用户数据、用户代码、中间结果表生成。

产品必须禁止：

* agent 自己编造数据
* demo 数值混入真实结果
* 修改视觉时误改统计结果
* 图中标注和 CSV 不一致

所以需要一个强规则：

> **Data layer 和 Visual layer 分离。**

数据层负责计算，视觉层只负责表达。

---

## 5.2 Figure Spec 中间表示

必须设计一个结构化 `figure.yaml` 或 `figure.json`。

例如：

```yaml
figure:
  id: fig2_proxy_validity
  journal_preset: nature_comm
  canvas:
    width_mm: 183
    height_mm: 125
  typography:
    font_family: Arial
    base_size_pt: 6.5
  panels:
    - id: A
      type: correlation_lollipop
      data: proxy_validity_correlations.csv
      x: spearman_rho
      y: proxy
      reference_line: 0
    - id: B
      type: auc_dotplot
      data: proxy_validity_auc.csv
      y: auc
      baseline: 0.5
    - id: C
      type: precision_lift
      data: proxy_validity_precision_lift.csv
    - id: D
      type: decile_curve
      data: proxy_validity_deciles.csv
```

agent 不应该直接“随便写 matplotlib”。
它应该先生成/修改 Figure Spec，再生成代码。

这带来几个好处：

* 修改可控
* 版本可比较
* 图表可复现
* 多图风格可统一
* 后续可以接不同渲染器

---

## 5.3 Skill-driven 图表系统

借鉴 Open Design 的 skills 思路，但我们做科研图表专用 skills。

第一版 skills 不要太多，但要狠。

---

# 6. MVP Skills 设计

## Skill 0：Figure Intent Parser

**作用：** 把自然语言需求转成结构化 figure plan。

输入：

> “我要画 Fig. 2，主题是 aboveground proxies weakly indicate SOCD，包含相关性、AUC、lift、decile 四个 panel，Nature 风格。”

输出：

```yaml
figure_story:
  claim: Aboveground proxies weakly indicate SOCD_0_30
  evidence_sequence:
    - weak rank correlation
    - near-random classification
    - low enrichment at high proxy quantiles
    - inconsistent decile response
  recommended_layout: 2x2
  required_inputs:
    - proxy_validity_correlations.csv
    - proxy_validity_auc.csv
    - proxy_validity_precision_lift.csv
    - proxy_validity_deciles.csv
```

这个 skill 决定“这张图到底要讲什么”。

---

## Skill 1：Journal Preset Skill

**作用：** 处理期刊规范。

内置 presets：

* Nature
* Nature Communications
* Science
* Cell
* PLOS
* Elsevier general
* IEEE two-column
* Thesis / Chinese dissertation

每个 preset 包括：

```yaml
journal_preset:
  figure_width_mm:
    single_column: 89
    double_column: 183
  font:
    family: Arial
    min_size_pt: 5
    normal_size_pt: 6.5
  export:
    vector: [pdf, svg, eps]
    raster: [png, tiff]
  line_width_pt:
    axis: 0.5
    data: 0.7
    border: 0.5
```

Nature 指南里明确提到初投稿图形可用 `.ai`, `.eps`, `.pdf`, `.ps`, `.svg` 等可编辑矢量格式，并建议最终尺寸下字体为 5–7 pt；这些可以直接变成 preset 规则。([Nature][4])

---

## Skill 2：Nature Figure Skill

可以借鉴 `nature-skills`，但要产品化。

`nature-skills` 的 `nature-figure` 目标已经包括 Nature 风格多面板 matplotlib、语义配色、可编辑 SVG 输出。 我们要把它扩展成可执行 skill：

### 它负责

* 多面板层级
* panel label
* 字号
* 留白
* 线宽
* 颜色
* 图例密度
* axes styling
* annotation style
* export parameters

### 关键原则

* 白底
* 信息密度高但不拥挤
* 不用廉价渐变
* 不用 3D
* 不用花哨阴影
* panel letter 简洁
* 数据点、线、误差条要克制
* 注释必须服务于结论

---

## Skill 3：Plot Family Skills

第一版支持 10 类就够。

### 3.1 Scatter / regression skill

用于：

* proxy vs SOCD
* embedding vs prediction
* observed vs predicted
* residual diagnostics

功能：

* Spearman / Pearson 标注
* LOESS / linear fit
* confidence band
* density scatter
* rank-rank scatter
* decoupling tails annotation

---

### 3.2 Dot / lollipop skill

用于：

* correlation ranking
* feature importance
* model gain
* variable effects

你的 SOC 研究里特别常用：

* Spearman rho horizontal plot
* ΔR² model gain plot
* AUC dotplot
* distance-aware validation dotplot

---

### 3.3 Box / violin / raincloud skill

用于：

* land cover groups
* climate zones
* diagnostic classes
* mismatch classes

---

### 3.4 Heatmap skill

用于：

* correlation matrix
* VIF / collinearity
* land-cover × mismatch
* region × proxy performance

---

### 3.5 ROC / PR / lift skill

用于：

* top-20% SOCD detection
* proxy validity
* classification diagnostic

---

### 3.6 Decile / quantile response skill

用于：

* proxy decile vs SOCD
* ASI rank binning
* top-k enrichment

---

### 3.7 Map panel skill

第一版不要试图替代 ArcGIS/QGIS，但要支持三种模式：

1. **placeholder map panel**
   只画空框，标注 “Map prepared in ArcGIS Pro”。

2. **simple vector map panel**
   用 GeoPandas/Cartopy 画基础边界、点、色带。

3. **hybrid map panel**
   地图底图作为 raster，文字、比例尺、图例、箭头、panel label 作为 vector。

第三种非常适合你之前提到的“半矢量 PDF”。

---

### 3.8 Conceptual schematic skill

用于：

* mechanism figure
* framework figure
* synthesis figure
* study design figure

但要注意：
这个 skill 不应该生成 AI 插画图，而应该生成**可编辑矢量结构图**：

* boxes
* arrows
* icons
* gradients only if controlled
* text layers
* evidence strip
* small vector mini-panels

---

### 3.9 Multi-panel assembler skill

这是 MVP 的核心之一。

它负责把不同来源的 panel 拼成完整 Figure。

可以借鉴 `figquilt` 的方向：用 YAML/JSON 布局文件组合 PDF/SVG/PNG 成 publication-ready figure，而且语言无关，支持来自 R、Python、Julia、Inkscape 等不同工具的 panel。([PyPI][1])

我们可以做自己的简化版：

```yaml
layout:
  type: grid
  rows: 2
  cols: 2
  ratios:
    width: [1, 1]
    height: [1, 1]
  panels:
    A: {row: 1, col: 1}
    B: {row: 1, col: 2}
    C: {row: 2, col: 1}
    D: {row: 2, col: 2}
```

---

### 3.10 Export / preflight skill

负责最终检查和导出：

* PDF
* SVG
* PNG 600 dpi
* TIFF 300/600 dpi
* source code
* figure spec
* data manifest

Nature 图形指南强调尽量导出可编辑矢量图层，不要把文字转轮廓，并给出了 matplotlib PDF fonttype 设置建议。([自然研究图示指南][3]) 这应该直接写进 export skill。

---

# 7. QA Skills：这是产品成败关键

普通 AI 画图的问题是：
它只生成，不审稿。

Open Figure Lab 必须有强 QA。

## 7.1 Data Integrity QA

检查：

* 图中所有数值是否来自数据文件
* 注释中的 rho / p / AUC / ΔR² 是否和表格一致
* 是否存在 demo/random/fake values
* 是否存在空值被错误处理
* panel 数据源是否记录完整

输出：

```text
PASS: Panel B AUC baseline = 0.5
PASS: All AUC values match proxy_validity_auc.csv
WARNING: Panel C uses top10_precision but axis label says top20_precision
FAIL: Annotation rho=0.21 not found in source table
```

---

## 7.2 Journal Compliance QA

检查：

* 字号
* 线宽
* 分辨率
* 格式
* 图层是否可编辑
* 字体是否嵌入
* 是否文字转曲
* 是否超出期刊宽度

PLOS 的指南明确要求图中文字使用 Arial、Times 或 Symbol，字号 8–12 pt，并提醒不能通过简单提高分辨率修复低分辨率图，也不要拖拽/复制粘贴导致 72 dpi 图片。([PLOS][6]) 这类规则也可以写成 PLOS preset 的 QA 检查。

---

## 7.3 Visual Hierarchy QA

检查：

* 是否有主视觉层级
* panel label 是否清晰
* legend 是否冗余
* axes 是否过重
* 颜色是否过多
* 留白是否合理
* 是否存在视觉噪声

---

## 7.4 Accessibility QA

检查：

* 色盲友好
* 不只依赖颜色区分
* 线型/点型是否区分
* 图注是否足够解释
* 导出是否支持 alt text

这里可以借鉴 MatplotAlt 这类思路。MatplotAlt 是一个给 matplotlib 图自动生成和展示 alt text 的开源 Python 包，论文也指出 LLM 直接描述图可能出现事实错误，需要结合启发式 alt text 或图中数据表来提升准确性。([arXiv][7]) 这对我们很有启发：图注/alt text 生成不能只靠视觉模型，必须绑定 Figure Spec 和数据表。

---

# 8. Revision Loop：最重要的交互体验

这个产品一定要围绕“改图”设计，而不是围绕“一次生成”。

用户真实需求是：

> “A 太窄了，B/C 字体小一点，D 的图例放右下角，整体更像 Nature，不要动数据。”

所以需要一个 revision agent。

## Revision skill 应该支持

### 几何修改

* “把 A 加宽 15%”
* “上面一行加高”
* “panel 间距缩小”
* “整个图保持 183 mm 宽”
* “A 必须是正方形”

### 样式修改

* “颜色更克制”
* “随机 CV 蓝色，空间 CV 绿色”
* “不要灰得发糊”
* “线宽统一”
* “字体改成 Arial”

### 语义修改

* “突出 ΔR² 接近 0”
* “把 mismatch tail 标出来”
* “不要暗示因果”
* “把 SoilGrids 标成 stress test”

### 约束修改

* “不要动数据”
* “不要重新计算模型”
* “只改 panel D”
* “保留 A 的地图占位框”

---

# 9. 产品界面设计

MVP 可以先不要做复杂桌面 app。
第一版可以是本地 Web UI。

## 推荐界面

### 左侧：Chat / Command

用户输入：

> “把 Fig. 3A 中心图保持正方形，上下空间加高，注释以后我自己调。”

### 中间：Figure Preview

显示：

* SVG/PDF/PNG 预览
* panel 点击选中
* 缩放
* 版本切换

### 右侧：Inspector

显示：

* Figure Spec
* panel size
* data source
* style tokens
* export options
* QA checklist

### 底部：Run log

显示：

* agent plan
* code changes
* QA result
* export files

这个结构和 Open Design 的产物优先思路很像：Open Design 里有 live agent panel、todo、tool calls、sandboxed preview、export 等机制。

---

# 10. 技术架构

## 10.1 总体结构

```text
Open Figure Lab
├── Agent Adapter
│   ├── OpenCode
│   ├── Codex
│   ├── Claude Code
│   └── Cursor
│
├── Skill Engine
│   ├── nature-figure
│   ├── journal-preset
│   ├── plot-family
│   ├── map-panel
│   ├── multi-panel-layout
│   ├── export-preflight
│   └── revision-diff
│
├── Figure Spec Engine
│   ├── figure.yaml
│   ├── theme.yaml
│   ├── data_manifest.yaml
│   └── version_history.json
│
├── Render Engine
│   ├── matplotlib
│   ├── plotnine
│   ├── geopandas/cartopy
│   ├── svgutils/cairo/resvg
│   └── optional Vega-Lite/Observable
│
├── QA Engine
│   ├── data integrity check
│   ├── visual check
│   ├── journal compliance check
│   └── export check
│
└── UI
    ├── chat
    ├── preview
    ├── inspector
    └── export panel
```

---

## 10.2 渲染引擎选择

### 第一主力：matplotlib

原因：

* 科研生态最稳
* PDF/SVG 导出成熟
* 可精细控制
* GIS/统计图兼容好
* agent 生成代码较可靠

### 第二层：plotnine / ggplot grammar

`plotnine` 是 Python 的 grammar-of-graphics 风格库，官方说明它借鉴 R ggplot2，可用组合式、层级化方式构建 publication-quality graphics。([Posit Open Source][8]) 它适合做更声明式的统计图 skill。

### 第三层：Vega-Lite / Altair / Observable Plot

这类适合：

* 交互预览
* 数据探索
* Web UI 中快速试图
* brush / filter / hover

Vega-Lite 官方定位是 high-level grammar for interactive graphics，也可作为声明式格式描述和创建可视化。([Vega][9]) Observable Plot 是开源 JS 库，面向表格数据探索，提供简洁 API 和 layered grammar of graphics。([GitHub][10])

但最终出版图，第一版还是建议以 matplotlib/SVG/PDF 为主。

---

# 11. 文件结构建议

MVP 项目可以这样组织：

```text
open-figure-lab/
├── app/
│   ├── web-ui/
│   └── api/
├── skills/
│   ├── nature-figure/
│   │   ├── SKILL.md
│   │   ├── rules.md
│   │   ├── templates/
│   │   └── examples/
│   ├── journal-preset/
│   ├── map-panel/
│   ├── multi-panel-assembler/
│   ├── export-preflight/
│   └── revision-diff/
├── packages/
│   ├── figure_spec/
│   ├── renderers/
│   ├── qa/
│   └── exporters/
├── examples/
│   ├── soc_proxy_fig2/
│   ├── spatial_mismatch_fig3/
│   └── model_gain_fig5/
├── workspace/
│   └── user_projects/
└── docs/
```

每个 figure project 里：

```text
fig2_proxy_validity/
├── data/
│   ├── proxy_validity_correlations.csv
│   ├── proxy_validity_auc.csv
│   └── ...
├── spec/
│   ├── figure.yaml
│   ├── theme.yaml
│   └── data_manifest.yaml
├── src/
│   └── render_fig2.py
├── outputs/
│   ├── fig2.svg
│   ├── fig2.pdf
│   ├── fig2.png
│   └── fig2_report.md
└── history/
```

---

# 12. 第一版最值得做的 8 个 Skills

我建议 MVP 先做这 8 个，别贪多。

## 1. `journal-preset-skill`

把 Nature / Science / Elsevier / PLOS 的格式要求变成 tokens。

## 2. `figure-spec-skill`

自然语言 → `figure.yaml`。

## 3. `nature-multipanel-skill`

2×2、1×3、map+plots、top schematic + bottom evidence strip。

## 4. `stat-plot-skill`

scatter、dotplot、lollipop、boxplot、heatmap、decile curve。

## 5. `map-placeholder-and-hybrid-skill`

解决 GIS 图最痛的地方：地图可以外部做，但排版、图例、文字、比例尺由系统接管。

## 6. `conceptual-schematic-skill`

做机制图、框架图、技术路线图，不依赖 AI 位图。

## 7. `publication-qa-skill`

审查图是否真的能投稿。

## 8. `revision-diff-skill`

让用户自然语言改图，并把修改映射到 spec/code。

---

# 13. 一个真实使用流程

用户输入：

> 生成 Fig. 5：model gain and spatial validation stress tests。A 是模型对比概念图，B 是 Random CV 和 Spatial CV 的 ΔR²，C 是 distance-aware validation，D 是 SoilGrids stress test。Nature 风格，ΔR² 坐标轴以 0 为中心，Random CV 蓝色，Spatial CV 绿色，输出 PDF/SVG/PNG。

系统流程：

```text
1. Intent Parser 解析图的科学叙事
2. Data Registry 检查需要哪些 CSV
3. Figure Spec 生成 figure.yaml
4. Plot Skills 生成各 panel
5. Multi-panel Assembler 拼图
6. QA 检查数据、字体、线宽、格式
7. Export 输出 SVG/PDF/PNG
8. 用户继续自然语言修改
```

用户修改：

> B 的 x 轴范围改成 -0.014 到 0.014，C 的点标注放右侧，D 标题去掉，只保留 panel letter。

系统只改 spec 和相关绘图代码，不重算数据。

---

# 14. 这个产品最该避开的坑

## 坑 1：一开始就做通用设计软件

不要。
MVP 必须只做科研图表。

## 坑 2：让 agent 自由发挥太多

科研图表不能“vibe design”。
必须是：

```text
spec → render → QA → revision
```

## 坑 3：只输出图片，不输出代码

不可接受。
必须输出：

* source code
* figure spec
* data manifest
* export files

## 坑 4：只支持单图

真正痛点是多面板 figure。
单图 matplotlib 已经能解决 60%，多面板拼图和修改才是价值核心。

## 坑 5：过度追求 AI 插画

你的需求不是“漂亮插图”，而是：

* 真实数据图
* 可编辑图层
* 稳定排版
* 期刊级导出

概念图可以有插图，但必须尽量矢量化、结构化。

---

# 15. MVP 功能清单

## 必须有

* 本地项目管理
* CSV/XLSX 数据导入
* 自然语言生成 figure plan
* `figure.yaml`
* matplotlib 渲染
* 多面板布局
* Nature preset
* SVG/PDF/PNG 导出
* QA report
* 自然语言修改
* 版本历史

## 可以后置

* Figma 插件
* Illustrator 插件
* Origin 控制
* QGIS 控制
* WebGL 交互
* AI 插画生成
* 自动论文图注生成
* 自动从论文 PDF 学习风格

---

# 16. 第一版 Demo 最好选什么？

我建议直接用你自己的 SOC 研究做 demo，因为它非常适合展示产品价值。

## Demo 1：Fig. 2 proxy validity

四个 panel：

* A: Spearman rho lollipop
* B: AUC dotplot with 0.5 baseline
* C: top-k precision/lift
* D: decile response

卖点：

* 真实数据
* 多图统一
* 很容易看出 Nature 风格提升

---

## Demo 2：Fig. 3 spatial mismatch

四个 panel：

* A: diagnostic quadrant / rank-rank schematic
* B: land-cover mismatch distribution
* C: regional mismatch rate
* D: context-conditioned mismatch

卖点：

* 混合概念图 + 数据图
* 展示复杂多面板修改能力

---

## Demo 3：Fig. 5 model gain

四个 panel：

* A: model comparison diagram
* B: ΔR² under random/spatial CV
* C: distance-aware validation
* D: SoilGrids stress test

卖点：

* ΔR² 接近 0 的精细表达
* 坐标轴、基准线、注释非常适合 QA

---

# 17. 技术 MVP 开发路线

## Week 1：命令行版本

目标：不用 UI，先跑通产物链。

```bash
ofl init fig2_proxy_validity
ofl add-data data/*.csv
ofl generate "Nature-style 2x2 figure about weak proxy validity"
ofl render
ofl qa
ofl export --svg --pdf --png
```

## Week 2：Figure Spec + Skills

完成：

* `figure.yaml`
* `theme.yaml`
* `journal_preset.yaml`
* `nature_multipanel.py`
* `qa_report.md`

## Week 3：Revision Loop

支持：

```bash
ofl revise "make panel A square and reduce vertical whitespace"
ofl revise "change Random CV to blue and Spatial CV to green"
ofl revise "do not alter data, only adjust visual layout"
```

## Week 4：Web UI

做最小界面：

* 左侧 chat
* 中间 preview
* 右侧 spec inspector
* export button

---

# 18. 最小可行架构：真的可以这样做

第一版甚至可以非常简单：

```text
OpenCode
  ↓
skills/*.md
  ↓
figure.yaml
  ↓
render.py
  ↓
fig.svg / fig.pdf / fig.png
  ↓
qa_report.md
```

这已经能比普通“让 Codex 写 matplotlib”强很多。

关键不是技术难，而是：

* skill 写得够专业
* spec 设计得够稳
* QA 足够严格
* 修改闭环足够好

---

# 19. 我建议的产品口号

可以这样定位：

## **From data to publication figure, with agentic precision.**

中文：

## **从数据到出版级论文图：可控、可改、可复现。**

或者更直接：

## **不是 AI 画图，而是 AI 参与科研图表生产。**

---

# 20. v1 总结

**Open Figure Lab v1 的核心不是“大而全”，而是做一个极强的科研多面板图工作台。**

最小闭环是：

```text
数据 → Figure Spec → Skill 渲染 → QA 检查 → 自然语言修改 → 出版级导出
```

第一版重点做：

1. Nature 风格多面板图
2. 真实数据绑定
3. 可编辑 SVG/PDF
4. 自然语言改图
5. 图表 QA
6. 代码和结果完全可复现

这个方向我认为非常值得推进，而且比“AI 控制 Origin/Figma”更现实。Origin/Figma 是后期精修工具；我们真正应该做的是前面的 **科研图表生产系统**。

[1]: https://pypi.org/project/figquilt/0.1.10/?utm_source=chatgpt.com "figquilt · PyPI"
[2]: https://arxiv.org/abs/1910.00279?utm_source=chatgpt.com "pylustrator: Code generation for reproducible figures for publication"
[3]: https://research-figure-guide.nature.com/figures/preparing-figures-our-specifications/?utm_source=chatgpt.com "Preparing figures - our specifications | Nature research figure guide"
[4]: https://www.nature.com/nature/for-authors/initial-submission?utm_source=chatgpt.com "Initial submission | Nature"
[5]: https://www.elsevier.com/about/policies-and-standards/author/artwork-and-media-instructions/artwork-overview?utm_source=chatgpt.com "Artwork overview | Elsevier policy"
[6]: https://journals.plos.org/plosone/s/figures?utm_source=chatgpt.com "PLOS One"
[7]: https://arxiv.org/abs/2503.20089?utm_source=chatgpt.com "MatplotAlt: A Python Library for Adding Alt Text to Matplotlib Figures in Computational Notebooks"
[8]: https://opensource.posit.co/software/plotnine/?utm_source=chatgpt.com "plotnine :: Posit Open Source"
[9]: https://vega.github.io/vega-lite/?utm_source=chatgpt.com "A High-Level Grammar of Interactive Graphics | Vega-Lite"
[10]: https://github.com/observablehq/plot?utm_source=chatgpt.com "GitHub - observablehq/plot: A concise API for exploratory data visualization implementing a layered grammar of graphics · GitHub"