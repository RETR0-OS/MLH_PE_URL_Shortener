#!/bin/sh
set -e

TEMPLATE="/etc/alertmanager/alertmanager.yml"
CONFIG="/etc/alertmanager/config.yml"
DISCORD_TEMPLATE="/etc/alertmanager/discord-receivers.yml"

cp "$TEMPLATE" "$CONFIG"

sed -i "s|\${RESEND_API_KEY}|${RESEND_API_KEY}|g" "$CONFIG"
sed -i "s|\${ALERT_EMAIL_TO}|${ALERT_EMAIL_TO}|g" "$CONFIG"

if [ -n "$DISCORD_WEBHOOK_URL" ]; then
  # Add discord routes: duplicate critical route to discord, add warnings route
  sed -i '/receiver: "email-critical"/a\
      continue: true\
    - match:\
        severity: critical\
      receiver: "discord-critical"\
      group_wait: 0s\
      repeat_interval: 15m\
    - receiver: "discord-warnings"\
      continue: true' "$CONFIG"

  # Append discord receivers under the existing receivers: block
  echo "" >> "$CONFIG"
  cat "$DISCORD_TEMPLATE" >> "$CONFIG"
  sed -i "s|\${DISCORD_WEBHOOK_URL}|${DISCORD_WEBHOOK_URL}|g" "$CONFIG"
fi

exec /bin/alertmanager --config.file="$CONFIG" "$@"
