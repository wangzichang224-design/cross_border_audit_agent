# 课堂局域网演示 Runbook

## 1. 确认项目目录

```powershell
cd D:\03_AI_Projects\cross_border_audit_agent\cross_border_audit_agent
```

## 2. 获取 WLAN IP

```powershell
Get-NetIPAddress -AddressFamily IPv4 |
  Where-Object { $_.InterfaceAlias -eq "WLAN" -and $_.AddressState -eq "Preferred" } |
  Select-Object -ExpandProperty IPAddress
```

当前机器最近一次检测到的 WLAN IP 是：

```text
10.5.52.230
```

如果课堂网络变化，以当天命令输出为准。

## 3. 启动前端

```powershell
streamlit run streamlit_app.py --server.address 0.0.0.0 --server.port 8501
```

本机打开：

```text
http://localhost:8501
```

同一局域网内打开：

```text
http://<WLAN-IP>:8501
```

例如：

```text
http://10.5.52.230:8501
```

## 4. 开场 Demo 流程

1. PPT 第 1 页展示局域网地址。
2. 浏览器打开前端。
3. 点击“使用内置示例生成底稿”。
4. 等待生成成功后点击下载 Excel。
5. 打开 Excel，重点展示：
   - 客户信息和期末日已写入；
   - 试算平衡表、银行账户、函证余额被结构化；
   - 公式区、Check 行、Tie-out 逻辑保留；
   - demo 默认 mock，不调用远端 API。

## 5. 备用 CLI 演示

如果网络或浏览器临时异常，用 CLI 跑同一条核心链路：

```powershell
python cli.py workpaper --case-type cash --mode mock `
  --materials-dir benchmarks/materials/case_001_minimal `
  --template-root outputs/clean_templates `
  --template-keyword 核心优化版
```

输出目录：

```text
output/workpapers/
```

## 6. 风险提示

- 课堂演示使用合成材料，不展示真实客户资料。
- 默认 mock 模式无需 API Key，也不会外发数据。
- 如需 `autogen` 模式，请先脱敏材料并确认 `.env` 配置。
