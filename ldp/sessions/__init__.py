"""The five debugging sessions. Each module has build(variant) -> SessionSpec."""
import importlib

MODULES = {
    "S1": "s1_coupon",     # hands on the app
    "S2": "s2_slow",       # hands on the app
    "S3": "s3_flaky",      # hands free
    "S4": "s4_crashloop",  # hands free
    "S5": "s5_warning",    # hands on the app
}
HANDS_ON = {"S1", "S2", "S5"}
N_VARIANTS = 20


def build(sid: str, variant: int):
    mod = importlib.import_module(f"{__name__}.{MODULES[sid]}")
    return mod.build(variant)
