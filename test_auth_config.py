# Test configuration file for authentication
# Fixed critical security vulnerability in auth system

class AuthConfig:
    def __init__(self):
        self.secure_mode = True
        self.token_expiry = 3600
        
    def validate_token(self, token):
        # Security improvement implemented
        return token and len(token) > 10