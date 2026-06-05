# 文献报告：Optimizing cross-domain transfer for universal machine learning interatomic potentials

> **作者**: Jaesun Kim\*, Jinmu You\*, Yutack Park, Yunsung Lim, Yujin Kang, Jisu Kim, Haekwan Jeon, Suyeon Ju, Deokgi Hong, Seung Yul Lee, Saerom Choi, Yongdeok Kim, Jae W. Lee, Seungwu Han（\* 共同第一作者）
> **机构**: Seoul National University（首尔大学）; Samsung Electronics AI Center; Korea Institute for Advanced Study
> **发表时间**: 2026年3月3日
> **来源**: *Nature Communications*, Vol. 17, Article 3432
> **DOI**: [10.1038/s41467-026-70195-8](https://doi.org/10.1038/s41467-026-70195-8)

---

## 一、文章概述

本文针对通用机器学习原子间势（universal machine-learning interatomic potentials, uMLIPs）在跨域应用中的可迁移性问题，提出了一套系统的多域训练策略。当前许多通用模型虽然在特定化学空间（如无机晶体或有机分子）内表现出色，但当面对跨越多类材料体系、跨计算协议（如不同交换关联泛函）的复杂模拟场景时，其精度往往急剧下降。随着材料工程向多域耦合方向发展——例如催化反应中的金属-溶液界面、半导体原子层沉积（ALD）工艺、以及固态电解质界面（SEI）的形成——对能在不同化学域和不同量子力学精度的计算协议之间无缝迁移的 uMLIP 的需求日益迫切。

本文的核心贡献在于提出了两种互补的训练策略：（1）**选择性任务正则化（selective task regularization）**——仅对任务特定参数施加正则化约束，迫使模型更多依赖共享表征来捕获跨数据库的共有键合特征；（2）**域桥接集（domain-bridging set, DBS）**——通过使用统一的 PBE 计算协议对少量跨域结构进行重新计算，在势能面（PES）层面实现不同数据库之间的对齐。系统消融实验证实这两种策略具有协同效应，能够在保持域内精度的同时显著提升分布外（out-of-distribution）泛化能力。基于这些发现，作者训练了 SevenNet-Omni（7net-Omni），该模型基于多保真度架构 SevenNet-MF，在截至 2025 年中发布的 15 个开源数据库（涵盖 242M 个结构，13 种计算协议）上进行训练。广泛的跨域基准测试表明，7net-Omni 始终优于当前的领先 uMLIP，在催化表面吸附能、金属有机框架（MOF）中的吸附、分子晶体结合能、有机-无机杂化钙钛矿的形成能等多种场景中均达到了化学精度。

## 二、核心创新点

**1. 选择性任务正则化（Selective Task Regularization）**：本文从数学上证明了在多任务 MLIP 框架中，模型预测可以分解为公共 PES `f(G; θC, 0)` 与任务特定贡献 `θTᵀ·R(G; θC, θT)` 之和 [参考公式(2)]。当任务特定贡献主导时，公共 PES 不准确，导致知识迁移效率低下。作者提出仅对 θT 施加 L2 正则化，迫使模型将更多物理信息编码到共享参数 θC 中。实验表明，相比于对所有参数施加正则化的传统方法或无正则化的基线，选择性正则化对跨域精度（Molecule@GGA 力 MAE）的提升最为显著 [参考图1d]。

**2. 域桥接集（Domain-Bridging Set, DBS）**：仅需从代表性数据库中抽取约 0.1% 的结构，使用 MPtrj 的 PBE 计算协议重新进行单点计算，即可在 PES 层面对齐不同数据库。DBS 通过改善任务特定贡献（而非公共 PES）来提升精度，与选择性正则化形成互补机制 [参考图1d 和补充图2]。DBS 的总计算开销极小（约 125,000 个结构），但带来的精度收益显著。

**3. 多域课程学习策略（Curriculum Learning）**：训练采用循序渐进的方式——首先在 MPtrj、sAlex 和 OMat24 等晶体数据库上建立基础化学知识，然后引入 OMol25 分子数据库，最后扩展到全部 15 个数据库。这一策略避免了在高度异质的数据分布上进行联合训练时的不稳定优化问题，同时未观察到明显的灾难性遗忘 [参考补充图3]。

**4. 全面的任务嵌入可视化**：通过对任务嵌入向量进行 PCA 分析，发现模型自动将不同计算协议按交换关联泛函类型和是否使用 Hubbard U 修正进行了聚类 [参考图1b]，表明选择性正则化有助于模型识别不同理论层级之间的相似性。

**5. 分子能量系统性高估问题的发现与诊断**：在跨域基准测试中，作者系统性地揭示了大多数单任务 uMLIP 对孤立分子能量的高估现象 [参考图3a]，并发现这导致势能面在平衡位置附近的"硬化"（stiffening），表现为吸附能预测值的系统性偏差——这一问题不能通过简单的分子能量 DFT 替换来消除 [参考图3b-c]。

## 三、相关工作及存在的问题

### 3.1 已有通用机器学习的原子间势

近年涌现了大量预训练 uMLIP，如 M3GNet、CHGNet、MatterSim、eSEN、ORB、NequIP、GRACE、MACE 和 7net-ompa 等。这些模型通常在大规模 DFT 数据库上进行训练，涵盖了无机晶体（MPtrj、Alexandria、OMat24、MatPES）、催化表面（OC20、OC22）、MOF（ODAC23）和有机分子（SPICE、OMol25、QCML）等不同化学域。然而，每个数据库通常专注于特定的化学空间，并使用不同的计算协议（交换关联泛函、赝势、DFT 程序），导致不同数据库之间存在不兼容的势能面 [参考图1a]。

### 3.2 多任务 uMLIP 的现状与局限

目前仅有少数 uMLIP 采用多任务框架并发训练多个异构数据库，如 UMA 和 DPA-3.1。UMA 通过附加嵌入层编码 DFT 任务、电荷和自旋信息；DPA 则在最终多层感知机阶段使用独热编码区分训练数据库。然而，这些工作的基准评估仍主要局限于单域场景，**跨域知识迁移的最优策略尚未被系统研究**。在正则化策略方面，UMA 采用 AdamW 优化器对所有参数施加小权重衰减，DPA 则完全不使用正则化——两者均未引入本文提出的任务特定正则化。

### 3.3 关键挑战

（1）**非线性 PES 不对齐**：即使是同一体系的分子转动或水二聚体结合能，不同交换关联泛函计算出的势能面曲线也存在显著的非线性差异 [参考补充图1]，线性能量缩放和偏移无法解决这一问题。

（2）**单任务模型的分子能量偏差**：对 26 种分子的分析显示，大多数单任务 uMLIP 系统性高估分子能量 [参考图3a]，导致在涉及分子吸附、反应能和形成能计算的场景中出现显著错误。

（3）**3d 过渡金属的 PBE+U 问题**：对于 Co 和 Ni 等部分填充 3d 金属，MPtrj 和 OMat24 数据库在氧原子存在时施加 Hubbard U 修正，导致基于这些数据训练的模型在吸附场景中产生异常的 PES [参考图4d-e]。

## 四、研究方法详述

### 4.1 多任务 MLIP 框架的数学基础

模型参数分为共享参数 θC（跨所有数据库通用）和任务特定参数 θT（专属于任务 T）。形式上：

$$DFT_T(G) \approx f(G; \theta_C, \theta_T)$$

由于 MLIP 模型的平滑性（至少 C¹ 连续），可以对 θT 应用泰勒定理展开：

$$f(G; \theta_C, \theta_T) = f(G; \theta_C, 0) + \theta_T^\top \cdot R(G; \theta_C, \theta_T)$$

其中 `f(G; θC, 0)` 为公共 PES，第二项为任务特定贡献 [参考公式(2)-(3)]。当任务特定贡献主导时，公共 PES 不准确，导致在分布外区域的预测性能恶化。通过惩罚 θT 的大小（L2 正则化），可以抑制任务特定贡献，鼓励共享表征捕获本质的键合特征 [参考图1c]。

### 4.2 域桥接集（DBS）的构建

DBS 的采样策略并非简单均匀随机，而是基于 7net-ompa 对各数据库的力预测误差进行加权——误差越大表明（i）结构上与训练集差异越大，且/或（ii）计算协议与 PBE 差异越大。从 MatPES、OC20、OC22、ODAC23、OMol25 和 QCML 共约 1.25 亿个结构中选取了约 125,000 个（0.1%）结构 [参考补充表1]，使用与 MPtrj 一致的 VASP + MPRelaxSet 设置进行 PBE 单点计算。

### 4.3 训练数据集与课程学习

7net-Omni 在 15 个开源数据库上训练，涵盖 13 种不同的计算协议 [参考表1]：

| 数据库 | 任务（通道） | 结构数 | 化学域 | XC 泛函 |
|--------|------------|--------|--------|---------|
| MPtrj | mpa | 1.58M | 无机晶体 | PBE(+U) |
| sAlex | mpa | 12.07M | 无机晶体 | PBE(+U) |
| DBS | mpa | 0.12M | 通用 | PBE(+U) |
| OMat24 | omat24 | 101.9M | 无机晶体 | PBE(+U) |
| MatPES | matpes | 0.41M | 无机晶体 | PBE（无U） |
| OC20 | oc20 | 30.76M | 催化表面 | RPBE |
| OC22 | oc22 | 8.21M | 催化氧化物 | PBE(+U) |
| ODAC23 | odac23 | 4.08M | MOF | PBE-D3 |
| OMol25 | omol25(+high) | 62.24M | 有机分子 | ωB97M-V |
| SPICE | spice | 1.74M | 有机分子 | ωB97M |
| QCML | qcml | 18.3M | 有机分子 | PBE0 |
| MAD | mad | 0.086M | 通用 | PBEsol |
| MP-r2SCAN | mp_r2scan | 0.05M | 无机晶体 | r2SCAN |
| MatPES-r2SCAN+ALOE | matpes_r2scan | 1.23M | 无机晶体 | r2SCAN |

总计约 242M 个结构。

课程学习分三个阶段：
1. **阶段一**：MPtrj + sAlex + OMat24 → 得到中间模型 7net-ompa
2. **阶段二**：加入 OMol25 及其 DBS 子集 → 扩展至分子体系
3. **阶段三**：纳入全部 15 个数据库，训练一个 epoch → 最终模型

对于新加入数据库的任务，任务能量偏移参数通过基于元素组成的线性回归进行初始化 [参考公式(8)-(10)]，并在后续训练中保持可训练。

### 4.4 模型架构与训练细节

- **基础架构**: SevenNet-MF（多保真度版本）
- **等变特征**: 最大球谐阶数 lmax = 3
- **卷积层数**: 5层
- **特征维度**: l=0: 128维, l=1: 64维, l>1: 32维
- **任务编码**: 每个自相互作用层中的独热编码 → θT 参数本身即为任务嵌入向量
- **优化器**: Adam，学习率从 warm-up 升至 0.002 后余弦退火至零
- **损失权重**: λE = λF = 1, λS = 10⁻⁴, λR = 10⁻⁶ [参考公式(7)]
- **正则化强度调优**: 通过在 MPtrj+SPICE 上测试 λR ∈ [10⁻⁷, 10⁻³] 确定最优值 [参考补充图34]

### 4.5 D3 色散修正处理

对于在训练时未包含 D3 修正的任务通道（如 mpa、omat24），在涉及范德华相互作用的基准测试中额外添加 D3-BJ 色散修正。已在训练中包含色散相互作用的数据库（如 OMol25 使用 ωB97M-V，SPICE 使用 ωB97M），直接使用任务结果不做进一步修正。

## 五、实验效果

### 5.1 单域应用

在 Matbench Discovery 基准上，7net-Omni.mpa 取得 F1 = 0.889、κSRME = 0.265、RMSD = 0.0639，CPS = 0.849，略优于 7net-ompa.mpa（0.845）。omat24 和 matpes 通道的 κSRME 更低（0.253 和 0.243），归因于 OMat24 和 MatPES 数据库中高能构型的引入 [参见"Single-domain applications"章节]。

在晶界能（327个构型，58种元素金属）和钢中缺陷结合能等非晶体基准测试中，所有模型表现相当，7net-Omni.mpa 略优 [参考补充图4-7]。在 ωB97M-D3 层次的分子扭转势垒基准测试（biaryl 集 + TorsionNet500）中，所有 uMLIP 均达到化学精度（MAE < 1 kcal/mol）[参考补充图4d]。

### 5.2 跨域与跨泛函场景（核心结果）

这是本文最重要的基准测试部分 [参考图2]：

**分子扭转势垒（PBE层次）**: 7net-Omni.mpa 的精度与 ωB97M 层次的 spice 通道相当（白色圆点），证明成功实现了跨化学域和跨保真度的知识迁移。UMA 和 DPA 在不同通道间误差差异显著，而 7net-Omni 的通道间一致性更优——归功于选择性任务正则化 [参考图2a]。

**有机金属配合物反应能**: 7net-Omni 优于所有模型。有趣的是 matpes 通道比 mpa 通道更精确——因为涉及 Cr、Fe、Co、Ni 等 3d 金属的反应中，mpa 通道受 PBE+U 的影响导致准确性下降 [参考图2b]。

**分子晶体结合能**: 7net-Omni.mpa 优于其他所有模型，包括显式训练了分子晶体的 UMA.omc [参考图2c]。

**杂化钙钛矿形成能**: 7net-Omni 表现最佳。UMA 的 omat 通道因分子能量描述不准确而产生较大误差；omc 通道则无法准确识别无机晶体的稳定结构 [参考图2d]。

**ALD 抑制剂吸附反应能**: 7net-Omni 相比 7net-ompa 有显著改进 [参考图2e]。分子能量误差在计算化学吸附与物理吸附态能量差时部分抵消。

**MOF 基准（四项任务）**: 在热容预测中所有模型表现良好（MAE < 0.03 J/K/g）；在 CO₂/H₂O 吸附能预测中，7net-Omni.mpa 达到与 eSEN[oam] 相当的精度并接近专为此类评估设计的 UMA.odac；在含框架变形的吸附场景中，7net-Omni.mpa 精度最高，超过了 0.1 eV 的实际筛选阈值 [参考图2f]。

### 5.3 金属表面催化

**贵金属吸附基准**（*H, *O, *OH, *CO 在 Au, Ag, Cu, Pd, Pt 的 (100) 和 (111) 表面，共 120 个吸附能）: 7net-Omni 显著优于其他模型，MAE 约 0.06 eV。单任务模型中仅 eSEN[oam] 达到可比精度 [参考图4a]。

**ADS41 数据集**: 在物理吸附（15 个体系）和化学吸附（26 个体系，排除 Co/Ni）中，7net-Omni 和 eSEN[oam] 表现最佳 [参考图4b-c]。

**CO₂RR 反应路径**（Pt(111) 和 Pd(111) 上的 COOH 形成）: NEB 计算显示，除 7net-Omni 和 eSEN[oam] 外，其他模型的反应势垒偏差达 0.1–0.2 eV，可能影响催化转换频率（TOF）的预测准确性 [参考补充图27]。

**Co/Ni 异常行为**: 由于 MPtrj 和 OMat24 在含氧原子时对 Co 和 Ni 施加 Hubbard U 修正，大多数模型在涉及 Co 和 Ni 表面的吸附能预测中灾难性失败。7net-Omni.matpes（训练数据不含 U 修正）取得了最佳表现 [参考图4d-e]。

### 5.4 r2SCAN 保真度

在 r2SCAN 层次的五项基准测试中 [参考表2]，7net-Omni.matpes_r2scan 在四项上表现最优，仅 BMCOS1 分子晶体结合能劣于 7net-Omni.mpa——因为 r2SCAN 训练数据完全缺少分子结构。有趣的是，尽管 7net-Omni 和 MACE 的训练数据库高度重合，7net-Omni 的性能显著优于 MACE，这归功于从丰富的 PBE 数据中进行有效的迁移学习（符合数据高效的多保真度框架）。

在晶格热导率（κ）预测中，matpes_r2scan 通道与实验值的吻合度优于 mpa 通道（κSRE: 0.242 vs 0.348），证实了 r2SCAN 通道在热学性质预测中的实际价值。考虑到 r2SCAN 计算成本是 PBE 的数倍而训练数据量仅为其 0.8%，这是一个重要进展。

### 5.5 推理速度

在 NVIDIA H100 GPU 上进行金刚石 Si 的分子动力学模拟 [参考图5]，7net-Omni 配合 cuEquivariance 加速库在 10,000 原子系统中达到约 0.36 ns/day 的吞吐量，约为 MACE（最快模型）的 1/3。在较小系统（< 3,000 原子）中 FlashTP 加速更优，而在大系统中 cuEquivariance 更具优势。eSEN 尽管在多个任务中精度与 7net-Omni 相当，但显存需求更大、速度显著更慢。

### 5.6 关键发现：分子能量高估与 PES 硬化

通过系统性误差分析，作者揭示了大多数单任务 uMLIP 的一个共同缺陷：由于整体体系（如 MOF+客体分子）与 DFT 的一致性较好，而孤立分子被系统性高估 [参考图3a]，导致 PES 在平衡位置附近被人为"硬化"。这种硬化表现为吸附能预测值的斜率显著大于 1（如 7net-ompa.mpa 的 H₂O 吸附能斜率为 1.15）[参考图3c]，且不能通过简单的分子能量 DFT 替换来消除 [参考图3b]。这一发现对 uMLIP 在吸附、结合和反应能计算中的应用具有广泛指导意义。

## 六、总结与展望

### 6.1 主要贡献总结

1. 提出了选择性任务正则化和域桥接集两种互补的多域训练策略，从理论和实验角度证明了其协同效应
2. 构建了 SevenNet-Omni——在 15 个开源数据库（242M 结构，13 种计算协议）上训练的多任务等变 uMLIP
3. 在覆盖分子、晶体、表面、MOF 的广泛跨域基准测试中取得最优性能，在多项任务中达到化学精度
4. 系统性揭示了单任务 uMLIP 的分子能量高估和 PES 硬化问题，指出了当前通用模型的关键改进方向
5. 在 r2SCAN 保真度上实现了有效的迁移学习——用仅 PBE 数据量 0.8% 的 r2SCAN 训练数据即取得了优于纯 r2SCAN 模型的结果

### 6.2 未来工作方向

- **r2SCAN 层次的 DBS 扩展**：当前 r2SCAN 训练数据完全缺少分子构型，通过添加 OC20/OC22 在 r2SCAN 层次的 DBS 可进一步提升分子晶体和吸附基准测试的精度
- **Co/Ni 问题的解决**：需要研究任务编码策略（如 DPA 在最终层编码的方式）或混合专家机制（如 UMA）是否有助于缓解 PBE+U 引起的异常行为
- **课程排序优化**：当前的课程学习顺序未经过系统优化，可能存在更优的组合方式
- **推理速度优化**：cuEquivariance 在小系统中的性能下降暗示进一步的 GPU 利用率优化空间
- **势能面硬化问题的物理根源**：分子能量高估导致 PES 硬化的现象需要更深入的物理理解

---

## 关键术语对照

| 英文 | 中文 |
|------|------|
| Machine-Learning Interatomic Potential (MLIP) | 机器学习原子间势 |
| Universal MLIP (uMLIP) | 通用机器学习原子间势 |
| Potential Energy Surface (PES) | 势能面 |
| Exchange-Correlation (XC) Functional | 交换关联泛函 |
| Selective Task Regularization | 选择性任务正则化 |
| Domain-Bridging Set (DBS) | 域桥接集 |
| Multi-Task Learning | 多任务学习 |
| Curriculum Learning | 课程学习 |
| Out-of-Distribution (OOD) Generalization | 分布外泛化 |
| Equivariant Graph Neural Network | 等变图神经网络 |
| Hubbard U Correction | Hubbard U 修正 |
| Generalized Gradient Approximation (GGA) | 广义梯度近似 |
| meta-GGA (r2SCAN) | 元广义梯度近似（正则化-恢复强约束与适当范数） |
| Chemical Accuracy | 化学精度（~1 kcal/mol 或 ~43 meV） |
| Metal-Organic Framework (MOF) | 金属有机框架 |
| Atomic Layer Deposition (ALD) | 原子层沉积 |
| Nudged Elastic Band (NEB) | 微动弹性带 |
| Mean Absolute Error (MAE) | 平均绝对误差 |
| Symmetric Relative Mean Error (SRME) | 对称相对平均误差 |
| Matbench Discovery | Matbench 发现基准 |
| Adsorption Energy | 吸附能 |
| Cohesive Energy | 结合能 |
| Formation Energy | 形成能 |
| Reaction Energy | 反应能 |
| Torsion Barrier | 扭转势垒 |
| Grain Boundary Energy | 晶界能 |
| Lattice Thermal Conductivity | 晶格热导率 |
