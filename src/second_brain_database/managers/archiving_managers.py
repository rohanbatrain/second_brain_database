"""
GPGManager and TelegramManager design for encrypted archiving and Telegram delivery of buffer logs.
uv """
import os
import gnupg
import requests
from second_brain_database.config import settings

def get_app_data_dir(app_name="second_brain_database"):
    xdg_data_home = os.getenv("XDG_DATA_HOME", os.path.expanduser("~/.local/share"))
    app_data_dir = os.path.join(xdg_data_home, app_name)
    os.makedirs(app_data_dir, exist_ok=True)
    return app_data_dir

class GPGManager:
    """
    Implements GPG encryption of buffer logs before archiving or sending externally.
    Automatically generates a static keypair at first use and stores it in the app data directory.
    Supports key rotation by regenerating the keypair if requested.
    """
    def __init__(self, gpg_home: str = None, recipient: str = None, rotate: bool = False):
        # Use XDG data dir for secure, production-ready storage
        self.gpg_home = gpg_home or getattr(settings, "GPG_HOME", get_app_data_dir())
        self.gpg_home = os.path.expanduser(self.gpg_home)
        self.gpg = gnupg.GPG(gnupghome=self.gpg_home)
        self.key_id_file = os.path.join(self.gpg_home, "second_brain_gpg_key_id.txt")
        self.recipient = recipient or getattr(settings, "GPG_RECIPIENT", os.getenv("GPG_RECIPIENT"))
        self.passphrase = getattr(settings, "GPG_KEY_PASSPHRASE", "second_brain_static_gpg_passphrase")
        self.key_email = getattr(settings, "GPG_KEY_EMAIL", "second_brain@localhost")
        self.key_type = getattr(settings, "GPG_KEY_TYPE", "RSA")
        self.key_length = getattr(settings, "GPG_KEY_LENGTH", 2048)
        if rotate or not self._key_exists():
            self.recipient = self._generate_keypair()
        else:
            self.recipient = self._get_key_id()

    def _key_exists(self):
        return os.path.exists(self.key_id_file)

    def _get_key_id(self):
        with open(self.key_id_file, "r") as f:
            return f.read().strip()

    def _generate_keypair(self):
        input_data = self.gpg.gen_key_input(
            name_email=self.key_email,
            passphrase=self.passphrase,
            key_type=self.key_type,
            key_length=self.key_length
        )
        key = self.gpg.gen_key(input_data)
        key_id = str(key)
        with open(self.key_id_file, "w") as f:
            f.write(key_id)
        return key_id

    def encrypt_file(self, file_path: str, output_path: str = None) -> str:
        output_path = output_path or (file_path + ".gpg")
        with open(file_path, "rb") as f:
            status = self.gpg.encrypt_file(
                f,
                recipients=[self.recipient],
                output=output_path,
                always_trust=True
            )
        if not status.ok:
            raise RuntimeError(f"GPG encryption failed: {status.status}")
        return output_path

    def decrypt_file(self, encrypted_path: str, output_path: str = None) -> str:
        output_path = output_path or (encrypted_path + ".decrypted")
        with open(encrypted_path, "rb") as f:
            status = self.gpg.decrypt_file(f, output=output_path, passphrase=self.passphrase)
        if not status.ok:
            raise RuntimeError(f"GPG decryption failed: {status.status}")
        return output_path

class TelegramManager:
    """
    Implements sending buffer logs to Telegram after flush/archiving.
    """
    def __init__(self, bot_token: str = None, chat_id: str = None):
        # Prefer config/settings for all Telegram credentials
        self.bot_token = bot_token or getattr(settings, "TELEGRAM_BOT_TOKEN", os.getenv("TELEGRAM_BOT_TOKEN"))
        self.chat_id = chat_id or getattr(settings, "TELEGRAM_CHAT_ID", os.getenv("TELEGRAM_CHAT_ID"))
        self.api_url = f"https://api.telegram.org/bot{self.bot_token}/sendDocument"
        self.msg_url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"

    def send_file(self, file_path: str, caption: str = None) -> bool:
        with open(file_path, "rb") as f:
            files = {"document": f}
            data = {"chat_id": self.chat_id}
            if caption:
                data["caption"] = caption
            response = requests.post(self.api_url, data=data, files=files)
        return response.status_code == 200

    def send_message(self, message: str) -> bool:
        data = {"chat_id": self.chat_id, "text": message}
        response = requests.post(self.msg_url, data=data)
        return response.status_code == 200
