# 🚀 部署说明

每天 UTC+8 早上 8:00 自动抓微博/抖音/知乎/百度/贴吧/B 站/GitHub 飙升榜,生成 20 条短视频爆款选题,自动部署到 GitHub Pages。

## 使用

访问 `https://你的用户名.github.io/topic-picker/`,点击日期查看当天报告。

## 手动触发

在 repo 页面点 `Actions` → `Daily Topic Picker` → `Run workflow`。

## 修改推送时间

编辑 `.github/workflows/daily.yml`,改 `cron: "0 0 * * *"`:
- `0 0` = UTC 0:00 = UTC+8 早上 8:00
- `0 1` = UTC 1:00 = UTC+8 早上 9:00

## 可选:邮件推送

1. 申请 QQ 邮箱授权码(设置 → 账户 → 开启 SMTP)
2. repo `Settings` → `Secrets and variables` → `Actions` → `New repository secret`,加 4 个:
   - `SMTP_HOST` = `smtp.qq.com`
   - `SMTP_PORT` = `465`
   - `SMTP_USER` = `你的QQ@qq.com`
   - `SMTP_PASS` = `你的授权码`
3. 编辑 `.github/workflows/daily.yml`,在 commit 步骤后加:
   ```yaml
   - name: Send email
     if: env.SMTP_USER != ''
     env:
       SMTP_HOST: ${{ secrets.SMTP_HOST }}
       SMTP_PORT: ${{ secrets.SMTP_PORT }}
       SMTP_USER: ${{ secrets.SMTP_USER }}
       SMTP_PASS: ${{ secrets.SMTP_PASS }}
       TO_EMAIL: khai_sin1116@hotmail.com
     run: python emailer.py output/$(date -u +%Y-%m-%d).md
   ```
