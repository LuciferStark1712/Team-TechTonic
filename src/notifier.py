import os
from dotenv import load_dotenv
from twilio.rest import Client


def _get_env_value(*keys: str) -> str | None:
    for key in keys:
        value = os.getenv(key)
        if value is None:
            continue
        cleaned = value.strip().strip('"').strip("'")
        if cleaned:
            return cleaned
    return None


class TwilioNotifier:
    def __init__(self):
        load_dotenv()
        self.sid = _get_env_value("TWILIO_ACCOUNT_SID")
        self.token = _get_env_value("TWILIO_AUTH_TOKEN")
        self.from_num = _get_env_value("TWILIO_FROM_NUMBER", "TWILIO_FROM")
        self.to_num = _get_env_value("TWILIO_TO_NUMBER", "ALERT_TO")
        
        self.active = all([self.sid, self.token, self.from_num, self.to_num])
        
        if self.active:
            self.client = Client(self.sid, self.token)
        else:
            print("[TWILIO] Missing credentials in .env. SMS alerts disabled.")

    def send_alert(self, event_type: str, risk_score: float, explanation: str):
        if not self.active:
            return

        # Twilio trial accounts block long multi-segment messages (error 30044).
        # Keep alert text short and single-segment friendly.
        max_len = int(os.getenv("TWILIO_MAX_SMS_CHARS", "140"))
        brief_explanation = " ".join(str(explanation).split())
        message = (
            f"ThreatSense ALERT | Type:{event_type.upper()} | "
            f"Risk:{risk_score * 100:.1f}% | {brief_explanation}"
        )[:max_len]
        
        try:
            twilio_msg = self.client.messages.create(
                body=message,
                from_=self.from_num,
                to=self.to_num
            )
            print(
                f"[TWILIO] API accepted message sid={twilio_msg.sid} "
                f"status={twilio_msg.status} to={self.to_num}"
            )
            if getattr(twilio_msg, "error_code", None) or getattr(twilio_msg, "error_message", None):
                print(
                    f"[TWILIO] Delivery issue code={twilio_msg.error_code} "
                    f"message={twilio_msg.error_message}"
                )
        except Exception as e:
            print(f"[TWILIO] Failed to send SMS: {e}")
