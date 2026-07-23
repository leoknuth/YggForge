# 许可说明（Licensing）

## 结论：不要用 MIT / Apache

| 协议 | 个人用 | 免费商用 | 是否符合本项目目标 |
| --- | --- | --- | --- |
| MIT / Apache-2.0 / BSD | ✅ | ✅ 永久免费 | ❌ 无法向大公司收费 |
| GPL / AGPL | ✅ | ✅（只要遵守 copyleft） | ❌ 商用仍可不付钱 |
| 专有闭源 | ❌ 源码不公开 | 可收费 | ❌ 你打算 GitHub 公开代码 |
| **PolyForm Noncommercial 1.0.0** | ✅ | ❌ 须另购 | ✅ **推荐作为公开默认** |

本项目目标是：

1. 源码上 GitHub，方便个人学习、自用、非商业改进  
2. **商业用途 / 大公司使用须先联系沟通**，再支付双方协商的一次性费用 

因此采用：

```text
公开默认：PolyForm Noncommercial 1.0.0
商用路径：单独书面授权（一次性）
```

SPDX 标识：`PolyForm-Noncommercial-1.0.0`  
全文：<https://polyformproject.org/licenses/noncommercial/1.0.0>  
仓库内正文：根目录 [`LICENSE`](../../LICENSE)（含 `Required Notice`）、[`COMMERCIAL.md`](../../COMMERCIAL.md)（商用授权说明）。

## 公开许可覆盖什么

在 Noncommercial 下通常允许：

- 个人学习、实验、爱好项目  
- 无预期商业应用的研究与测试  
- 部分非营利/教育/政府等机构用途（见许可正文「Noncommercial Organizations」）

**不覆盖**（须另行商用授权）：

- 公司内部生产使用、对客户交付、SaaS/产品化  
- 以本软件承接付费项目作为主要工具  

边界案例（个人工作室、副业接单等）以许可正文为准；拿不准就按「先沟通」处理。联系：`leo_wgao@126.com`。

## 为何不选其它「限制商用」方案

| 方案 | 说明 |
| --- | --- |
| Commons Clause + Apache | 主要限制「卖软件本身」，**不一定**挡住公司免费内部用 |
| SSPL / BSL | 偏服务商竞争或「过期后变开源」，语义与「一次性买断」不同 |
| 自写「个人免费商用收费」短文 | 易有漏洞；GitHub/律师难认；维护成本高 |
| PolyForm Small Business | 小公司可免费商用；若你希望「凡商业都谈」，用 Noncommercial 更严 |

## GitHub 上架检查清单

1. ✅ `LICENSE`（含 `Required Notice`）与 `COMMERCIAL.md` 已提交入库  
2. ✅ README「License」一节链到上述文件  
3. ⚠️ 仓库 **Settings → General → License** 选 **Other**（PolyForm Noncommercial 不在 GitHub 标准许可证下拉列表里，无法自动识别）；切勿留空或误标 MIT/Apache，否则会被 GitHub 与依赖扫描工具当作「可免费商用」，与本项目意图相反。手动标注可在仓库根放一个 `LICENSE`（已入库）即可被 GitHub 识别为自定义许可。
4. 商用联系邮箱：`leo_wgao@126.com`  
5. 公开 `Required Notice` 可用 GitHub 账户名；**商用合同/发票主体**建议用真实姓名或公司名（不必公开在仓库里）  
6. 若有联合作者/职务作品，确认版权归属后再公开发布  
7. （可选）成交后用一页纸「Commercial License Grant」写明：买方实体、一次性费用、范围、是否可改/再分发  

## 相关

- [../../README.md](../../README.md)
- PolyForm Noncommercial 1.0.0：<https://polyformproject.org/licenses/noncommercial/1.0.0>
