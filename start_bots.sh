#!/bin/bash
PROJECT="/mnt/c/Users/A50529/Desktop/Craig/Antique Digital Pavilion"
SESSION="ap"
tmux has-session -t "$SESSION" 2>/dev/null && tmux kill-session -t "$SESSION"
tmux new-session -d -s "$SESSION" -n "antique-bot"
tmux send-keys -t "$SESSION:0" "cd \"$PROJECT\" && python3 -u ap_discord_bot.py" Enter
tmux new-window -t "$SESSION" -n "org-bot"
tmux send-keys -t "$SESSION:1" "cd \"$PROJECT\" && python3 -u scripts/ap_org_bot.py" Enter
echo "✅ Bots started in tmux session 'ap'"
echo "   View: tmux attach -t ap"
