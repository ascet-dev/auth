from datetime import timedelta

from pydantic_settings import BaseSettings


class Auth(BaseSettings):
    # JWT Configuration
    algorithms: list[str] = ["RS256"]
    access_token_lifetime: timedelta = timedelta(minutes=1)
    refresh_token_lifetime: timedelta = timedelta(days=30)

    # TEST/DEVELOPMENT KEYS ONLY - DO NOT USE IN PRODUCTION!
    # In production, load keys from environment variables
    public_key: str = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAtD/nFYH4CXN7Jy7zudpb
Wj+pghUczDQCX8rFMJDfWxyWlTy5Vc9/4/uNvOzMHzOJNix1Av08cvAkHkeLF3AK
fxUv2ADVr9LVbOEDTzvBQ1TqXmwOaplQD7mVxIqpiDES41S1ESlkK3gcu5dRfuxp
ZXJs9m2903Y1O0GphCK1XFCEkdjaffwNduAFYi/YPgo+0uM6O153DgQTQfz5THoM
+TNZNMR4ijtAyfIt/H7AsDHffJPUcQIBhiIQ6stEvrnG8wST2ZMT3kz3K1f3iEF/
586y+0quTF2pLXPQz8G6Pzslc0FVDKuU5TKmUFEv6I/l0G94LOKt21REeyRUucHW
awIDAQAB
-----END PUBLIC KEY-----
"""
    # TEST/DEVELOPMENT KEYS ONLY - DO NOT USE IN PRODUCTION!
    # In production, load private key from environment variable: JWT_PRIVATE_KEY
    private_key: str = """-----BEGIN RSA PRIVATE KEY-----
MIIEpQIBAAKCAQEAtD/nFYH4CXN7Jy7zudpbWj+pghUczDQCX8rFMJDfWxyWlTy5
Vc9/4/uNvOzMHzOJNix1Av08cvAkHkeLF3AKfxUv2ADVr9LVbOEDTzvBQ1TqXmwO
aplQD7mVxIqpiDES41S1ESlkK3gcu5dRfuxpZXJs9m2903Y1O0GphCK1XFCEkdja
ffwNduAFYi/YPgo+0uM6O153DgQTQfz5THoM+TNZNMR4ijtAyfIt/H7AsDHffJPU
cQIBhiIQ6stEvrnG8wST2ZMT3kz3K1f3iEF/586y+0quTF2pLXPQz8G6Pzslc0FV
DKuU5TKmUFEv6I/l0G94LOKt21REeyRUucHWawIDAQABAoIBAChrph34Gc/Awk68
pDI6yb6YxSHjKySNyzSBC6xC6JuNcyU/S053bDYLXLMPpQygKXZpDMphUHNz752M
rJ/SY8Aw15xIP6Mgk/TJFs1nWIUJX09SSv9TpxUHqJK9B5x/aL1q6vnQvuJSmprk
qYVdbZsuyEmQvX9UpEZICMQVZncvRNnMLLelrUM4QJjGWoPEldmZDtrVhberckFi
sq/Iq70jhnWAAKDbhoOzfVunhVWy69HPyMUQ3dxoQ9uGZmWS0zzkRucLLjcrIQXB
gAQqfIKe8WY/VfyX7f3jjiZLOM3LiE8uJ8oA2tx4AAR8qCEMPR1KF4ARHjjFgTPh
ayKHXvkCgYEA2VE8F2JmHfDxM+1/49rcyqDOpnBbi1QDkTVuZDjwHwvKvGtRrFtY
6t6uoLTABH9lstNOGducuWRBMlLNuredrZ1w5IUy9t7c1SKTIzNe/Xhc/DCbieNg
lwf0AzpP3aBkuegjKVxwO/zmyZf968iyfUL5JRhgtXSaxxcQIqS4RgMCgYEA1FWO
8tJiOoOmlZX54pDHb9H7EV6JOKViNFPw+RIw+Dd4WVJ+dRuAr7FzI84VV9gPZP2W
eUXx1n51cy6yMbRh7UBebfVy01o4bpfgDP45g9F60uldIz6H6sqJKkg+2SUiEcmp
a2nY7oF9u7y2OxSUYD5A/+RyQNT1HaqLua6jlXkCgYEA0NM+6zmi5yKgpUWTn2Cw
ygW8jjNpxHj29JJjges00qCCMIzv7q/Ywdk59TO7UJcbIrvqUO63q26rN7BaARJw
cmTYFr/oOVHu4uBWg3zZyrfeongS/m2AY6FA2dku5ck7AWoQX650KzDalN15Ixm4
aqXww7SpObTTBn0jBCdE7AECgYEAyzDw8aeoPmybbkwt68U2ROiBRTbdQ6roFkE5
uW/SEsYqUfficbiW5gp+r4XX4M8utCsD4xuu+N7dEBNgjLYcfAh8FOesMVsF47dM
vcJOUbmVut18tmxxbprQtfiaw/uH5dPAX7zTzjF2m8BT9qeT8aHBW99GAoqH4hLB
UTgw7KkCgYEAmMdNwdmiUzv+ZFJY5BP2HpnRTqBjv84PL13GvLvFBD4ZPnvFsVWC
JznMexvoqPBcexlDthimp/fZGx8NrqhvQnOeWiePCdUMRkkp/1c0zvPh9zZ+NCir
uF2ndSF/IXss+GMHYPwu3OgTD2NRGuVR+5LjiQPRnx861/djZbvh2ok=
-----END RSA PRIVATE KEY-----
"""
