import pyotp

secret = "5QTH5XXUR3PMCZ7J25A2RKALUA"

otp = pyotp.TOTP(secret).now()

print("Generated OTP:", otp)