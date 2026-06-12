# Claude Code 備份還原說明（還原卡電腦用）

學校電腦每次重開機 C 槽會被還原，Claude Code 存在 C 槽的東西都會消失：
對話紀錄、長期記憶、個人 skill、登入狀態。這個資料夾是它們的備份。

## 重開機後要做的事

1. **重新登入**：開 Claude Code 會要求登入，照常登入即可。

2. **Skill 不用還原**：skill 已經放在專案內的 `.claude/skills/`（D 槽），
   在這個專案裡會自動生效。若想在「其他專案」也能用，把它複製回 C 槽：

   ```powershell
   Copy-Item -Recurse "D:\AI Class ChenYu\AIClass\hw99\.claude\skills\pptx-to-animated-video" "$env:USERPROFILE\.claude\skills\"
   ```

3. **還原長期記憶**（讓 Claude 記得切圖規則和專案脈絡）：

   ```powershell
   New-Item -ItemType Directory -Force "$env:USERPROFILE\.claude\projects\D--AI-Class-ChenYu-AIClass-hw99\memory"
   Copy-Item "D:\AI Class ChenYu\AIClass\hw99\claude-backup\memory\*" "$env:USERPROFILE\.claude\projects\D--AI-Class-ChenYu-AIClass-hw99\memory\"
   ```

4. **還原對話紀錄**（想用 `claude --resume` 接續舊對話才需要）：

   ```powershell
   Copy-Item "D:\AI Class ChenYu\AIClass\hw99\claude-backup\conversation\*.jsonl" "$env:USERPROFILE\.claude\projects\D--AI-Class-ChenYu-AIClass-hw99\"
   ```

   然後在專案目錄執行 `claude --resume` 挑選對話。

## 之後每次下課前

把新的對話紀錄補進備份再推上 GitHub：

```powershell
Copy-Item "$env:USERPROFILE\.claude\projects\D--AI-Class-ChenYu-AIClass-hw99\*.jsonl" "D:\AI Class ChenYu\AIClass\hw99\claude-backup\conversation\" -Force
Copy-Item "$env:USERPROFILE\.claude\projects\D--AI-Class-ChenYu-AIClass-hw99\memory\*" "D:\AI Class ChenYu\AIClass\hw99\claude-backup\memory\" -Force
git add claude-backup .claude
git commit -m "backup claude session"
git push
```

（也可以在對話裡直接跟 Claude 說「幫我備份對話紀錄」，它會照這份文件做。）
