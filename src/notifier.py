import os
from dotenv import load_dotenv
from twilio.rest import Client

class TwilioNotifier:
    def __init__(self):
        load_dotenv()
        self.sid = os.getenv("TWILIO_ACCOUNT_SID")
        self.token = os.getenv("TWILIO_AUTH_TOKEN")
        self.from_num = os.getenv("TWILIO_FROM_NUMBER")
        self.to_num = os.getenv("TWILIO_TO_NUMBER")
        
        self.active = all([self.sid, self.token, self.from_num, self.to_num])
        
        if self.active:
            self.client = Client(self.sid, self.token)
        else:
            print("[TWILIO] Missing credentials in .env. SMS alerts disabled.")

    def send_alert(self, event_type: str, risk_score: float, explanation: str):
        if not self.active:
            return

        message = (
            f"🚨 ThreatSense ALERT!\n"
            f"Type: {event_type.upper()}\n"
            f"Risk: {risk_score * 100:.1f}%\n"
            f"Detail: {explanation}"
        )
        
        try:
            self.client.messages.create(
                body=message,
                from_=self.from_num,
                to=self.to_num
            )
            print(f"[TWILIO] Alert sent to {self.to_num}")
        except Exception as e:
            print(f"[TWILIO] Failed to send SMS: {e}")
