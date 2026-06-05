# Classroom Demo Runbook

This runbook is for the cross-border e-commerce fund-flow audit demo.

## 1. Start The App

```powershell
cd D:\03_AI_Projects\cross_border_audit_agent\cross_border_audit_agent
streamlit run streamlit_app.py --server.address 0.0.0.0 --server.port 8501
```

Check the WLAN IP before class:

```powershell
Get-NetIPAddress -AddressFamily IPv4 |
  Where-Object { $_.InterfaceAlias -eq "WLAN" -and $_.AddressState -eq "Preferred" } |
  Select-Object -First 1 -ExpandProperty IPAddress
```

Open:

```text
http://<WLAN-IP>:8501
```

## 2. Live Demo Flow

1. Open the front page: “跨境电商资金流 AI 审计系统”.
2. Keep data source as “演示数据（自动生成）”.
3. Keep simulated days at 90.
4. If API key is configured, keep DeepSeek enabled; otherwise use the rule report path.
5. Click “开始审计”.
6. Show the pipeline stages:
   - data ingestion
   - cleaning and quality score
   - ISA 240 / ISA 520 rule scan
   - optional DeepSeek narrative
   - settlement reconciliation
   - report generation
7. Show the result area:
   - key financial metrics
   - audit findings list
   - AI audit narrative
   - platform and cost charts
   - download buttons

## 3. Backup CLI Demo

If Streamlit is slow or the classroom network is unstable:

```powershell
python cli.py run --case-type cross_border --mode mock
```

Outputs:

```text
output/audit_reports/
```

## 4. Talking Points

- The demo data is synthetic and safe for class.
- The system is not a free-form chatbot; it is a controlled workflow.
- Rule checks catch deterministic issues first.
- AI narrative is useful for explaining risk, but human review remains the final gate.
- Real client data should be desensitized or processed in a private deployment.

## 5. Before Presenting

```powershell
python -m pytest -q
python cli.py doctor
python cli.py where
```

Confirm the PPT cover IP matches the current WLAN IP.
