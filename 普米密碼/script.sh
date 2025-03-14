# 寫入密碼（無換行）
echo -n "$SCRAPE_PASSWORD" > out/${CI_JOB_NAME}_password.txt
chmod 600 out/${CI_JOB_NAME}_password.txt

# 🔍 密碼不可為空
if [ -z "$SCRAPE_PASSWORD" ]; then
  echo "❌ 密碼變數 SCRAPE_PASSWORD 為空，請確認 GitLab Secret 設定"
  exit 1
fi

# 🔍 密碼僅允許單行
LINES=$(cat out/${CI_JOB_NAME}_password.txt | wc -l)
if [ "$LINES" -gt 1 ]; then
  echo "❌ 密碼檔案含多行，格式錯誤"
  exit 1
fi

# 🔍 密碼強度基本檢查（至少 8 字元、包含數字與英文字母）
if ! echo "$SCRAPE_PASSWORD" | grep -Eq '^(?=.*[A-Za-z])(?=.*[0-9]).{8,}$'; then
  echo "⚠️ 密碼強度過低，建議至少 8 字元，且包含數字與英文字母"
fi

echo "✅ 密碼檢查完成，開始產生 Prometheus 設定..."
