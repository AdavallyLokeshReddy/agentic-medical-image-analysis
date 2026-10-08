import numpy as np

from tools.pancreas_tumor_segmentation import (
    PancreasTumorSegmentationTool,
)


def run_test(name, function):
    try:
        function()

        print(
            f"{name}: FAIL - "
            "invalid input was unexpectedly accepted"
        )

        return False

    except Exception as exc:
        print(
            f"{name}: PASS - safely rejected "
            f"({type(exc).__name__}: {exc})"
        )

        return True


def main():
    print("CT-4 SAFETY TESTS START")
    print("=" * 60)

    tool = PancreasTumorSegmentationTool()

    tests = [
        (
            "NON_CT_MODALITY",
            lambda: tool.run(
                {
                    "modality": "MRI",
                    "series_dir": (
                        "uploads/"
                        "CASE-ABDOMEN-0001/"
                        "series"
                    ),
                }
            ),
        ),

        (
            "MISSING_INPUT",
            lambda: tool.run(
                {
                    "modality": "CT",
                }
            ),
        ),

        (
            "EMPTY_VOLUME",
            lambda: tool.predict_hu_volume(
                np.empty(
                    (0, 0, 0),
                    dtype=np.float32,
                ),
                (1.0, 1.0, 1.0),
            ),
        ),

        (
            "INVALID_SPACING",
            lambda: tool.predict_hu_volume(
                np.zeros(
                    (96, 96, 96),
                    dtype=np.float32,
                ),
                (0.0, 1.0, 1.0),
            ),
        ),

        (
            "NAN_VOLUME",
            lambda: tool.predict_hu_volume(
                np.full(
                    (96, 96, 96),
                    np.nan,
                    dtype=np.float32,
                ),
                (1.0, 1.0, 1.0),
            ),
        ),
    ]

    passed = 0

    for name, function in tests:
        if run_test(name, function):
            passed += 1

    total = len(tests)

    print()
    print("=" * 60)
    print(f"SAFETY TESTS PASSED: {passed}/{total}")
    print(f"SAFETY TESTS FAILED: {total - passed}/{total}")

    if passed == total:
        print("CT-4 SAFETY TESTS: PASS")
    else:
        print("CT-4 SAFETY TESTS: FAIL")


if __name__ == "__main__":
    main()