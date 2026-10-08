import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from verification.mri1_verification import MRI1VerificationEngine

verifier = MRI1VerificationEngine()

print("MRI1VerificationEngine.verify() return schema inspection")
print("Run the existing Step 15 test only after this inspection.")
print()
print("Verifier object:")
print(verifier)
print()
print("Public attributes:")
for name in dir(verifier):
    if not name.startswith("_"):
        print(" -", name)
