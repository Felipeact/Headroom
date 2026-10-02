import os

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey

# A key pair for this test session only. Its public half is CLERK_JWT_KEY for every test
# (process env beats .env.local), so tests sign their own tokens and never call Clerk.
TEST_PRIVATE_KEY: RSAPrivateKey = rsa.generate_private_key(
    public_exponent=65537, key_size=2048
)
TEST_PUBLIC_PEM = (
    TEST_PRIVATE_KEY.public_key()
    .public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    .decode()
)
os.environ["CLERK_JWT_KEY"] = TEST_PUBLIC_PEM
os.environ["CLERK_AUTHORIZED_PARTIES"] = ""
