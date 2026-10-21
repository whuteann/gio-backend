"""Bilingual bodies for the emails this app sends.

app/services/mail.py takes raw HTML, so the markup lives here rather than
being built at each call site. Every other user-facing string in this stack
exists in both `en` and `zh` (public/locales/{en,zh}/ on the frontend);
an English-only email would be the only exception, so each template takes
the recipient's `preferred_language`.

Kept to inline styles and a single table-free layout on purpose — mail
clients strip <style> blocks, and this only ever has to render a code.
"""

from app.config import settings

PASSWORD_RESET_CODE_TTL_MINUTES = 10

_RESET_SUBJECT = {
    "en": "Your Auren password reset code",
    "zh": "您的 Auren 密码重置验证码",
}

_RESET_BODY = {
    "en": """
<div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;max-width:480px;margin:0 auto;padding:32px 24px;color:#1c1917">
  <h1 style="font-size:20px;font-weight:600;margin:0 0 16px">Reset your password</h1>
  <p style="font-size:15px;line-height:1.6;margin:0 0 24px">
    Hi {display_name}, use this code to set a new password:
  </p>
  <p style="font-size:34px;font-weight:700;letter-spacing:10px;margin:0 0 24px;color:#0f172a">{code}</p>
  <p style="font-size:14px;line-height:1.6;color:#57534e;margin:0 0 8px">
    It expires in {ttl} minutes and can be used once.
  </p>
  <p style="font-size:14px;line-height:1.6;color:#57534e;margin:0">
    If you didn't ask to reset your password, you can ignore this email —
    nothing has changed.
  </p>
</div>
""",
    "zh": """
<div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;max-width:480px;margin:0 auto;padding:32px 24px;color:#1c1917">
  <h1 style="font-size:20px;font-weight:600;margin:0 0 16px">重置您的密码</h1>
  <p style="font-size:15px;line-height:1.6;margin:0 0 24px">
    {display_name} 您好，请使用以下验证码设置新密码：
  </p>
  <p style="font-size:34px;font-weight:700;letter-spacing:10px;margin:0 0 24px;color:#0f172a">{code}</p>
  <p style="font-size:14px;line-height:1.6;color:#57534e;margin:0 0 8px">
    验证码将在 {ttl} 分钟后失效，且仅可使用一次。
  </p>
  <p style="font-size:14px;line-height:1.6;color:#57534e;margin:0">
    如果这不是您本人的操作，请忽略此邮件——您的账户没有任何变动。
  </p>
</div>
""",
}


_VERIFY_SUBJECT = {
    "en": "Verify your Auren email",
    "zh": "验证您的 Auren 邮箱",
}

_VERIFY_BODY = {
    "en": """
<div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;max-width:480px;margin:0 auto;padding:32px 24px;color:#1c1917">
  <h1 style="font-size:20px;font-weight:600;margin:0 0 16px">Welcome to Auren</h1>
  <p style="font-size:15px;line-height:1.6;margin:0 0 24px">
    Hi {display_name}, use this code to verify your email and finish setting up your account:
  </p>
  <p style="font-size:34px;font-weight:700;letter-spacing:10px;margin:0 0 24px;color:#0f172a">{code}</p>
  <p style="font-size:14px;line-height:1.6;color:#57534e;margin:0 0 8px">
    It expires in {ttl} minutes and can be used once.
  </p>
  <p style="font-size:14px;line-height:1.6;color:#57534e;margin:0">
    If you didn't create an Auren account, you can ignore this email.
  </p>
</div>
""",
    "zh": """
<div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;max-width:480px;margin:0 auto;padding:32px 24px;color:#1c1917">
  <h1 style="font-size:20px;font-weight:600;margin:0 0 16px">欢迎来到 Auren</h1>
  <p style="font-size:15px;line-height:1.6;margin:0 0 24px">
    {display_name} 您好，请使用以下验证码验证邮箱，完成账户设置：
  </p>
  <p style="font-size:34px;font-weight:700;letter-spacing:10px;margin:0 0 24px;color:#0f172a">{code}</p>
  <p style="font-size:14px;line-height:1.6;color:#57534e;margin:0 0 8px">
    验证码将在 {ttl} 分钟后失效，且仅可使用一次。
  </p>
  <p style="font-size:14px;line-height:1.6;color:#57534e;margin:0">
    如果您没有注册 Auren 账户，请忽略此邮件。
  </p>
</div>
""",
}


def signup_verification_code(*, display_name: str, code: str, language: str) -> tuple[str, str]:
    """Returns (subject, html_body) for the signup email-verification code."""
    lang = language if language in _VERIFY_BODY else "en"
    body = _VERIFY_BODY[lang].format(
        display_name=display_name, code=code, ttl=PASSWORD_RESET_CODE_TTL_MINUTES,
    )
    return _VERIFY_SUBJECT[lang], body


def password_reset_code(*, display_name: str, code: str, language: str) -> tuple[str, str]:
    """Returns (subject, html_body). Falls back to English for any language
    that isn't `zh`, matching how `primary_language` is handled elsewhere."""
    lang = language if language in _RESET_BODY else "en"
    body = _RESET_BODY[lang].format(
        display_name=display_name,
        code=code,
        ttl=PASSWORD_RESET_CODE_TTL_MINUTES,
    )
    return _RESET_SUBJECT[lang], body
