#!/bin/sh
set -e

TEMPLATE="/etc/alertmanager/alertmanager.yml"
CONFIG="/etc/alertmanager/config.yml"

cp "$TEMPLATE" "$CONFIG"

sed -i "s|\${RESEND_API_KEY}|${RESEND_API_KEY}|g" "$CONFIG"
sed -i "s|\${ALERT_EMAIL_TO}|${ALERT_EMAIL_TO}|g" "$CONFIG"

exec /bin/alertmanager --config.file="$CONFIG" "$@"
