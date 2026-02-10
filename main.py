import argparse
from typing import Union

from settings import Settings
from models import (
    DebateSide,
    OutputFormat,
    StudentSubmission,
    UnderstoodArguments,
    PointsResponse,
    RebuttalParagraphs,
    ReferencedParagraphs,
    EvidenceBasedResponse,
)
from agent import build_client, understand_arguments, generate_counter


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--motion", required=True)
    p.add_argument("--side", choices=[s.value for s in DebateSide], required=True)
    p.add_argument("--format", dest="fmt", choices=[f.value for f in OutputFormat], required=True)
    p.add_argument("--argument", help="Student's argument text")
    p.add_argument("--argument_file", help="Path to a text file containing the student's argument")
    return p.parse_args()


def read_argument_text(arg: str | None, path: str | None) -> str:
    if arg:
        return arg
    if path:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    raise SystemExit("Provide --argument or --argument_file")


def main():
    settings = Settings()
    settings.init_observability()

    client = build_client(settings)

    args = parse_args()
    argument_text = read_argument_text(args.argument, args.argument_file)

    submission = StudentSubmission(
        motion=args.motion,
        student_side=DebateSide(args.side),
        argument_text=argument_text,
        requested_format=OutputFormat(args.fmt),
    )

    try:
        print("[understand] start")
        understood: UnderstoodArguments = understand_arguments(
            submission=submission,
            client=client,
            settings=settings,
            span_attrs={
                "motion": submission.motion,
                "student_side": submission.student_side.value,
            },
        )
        print("[understand] done")

        print("[counter] start")
        result: Union[PointsResponse, RebuttalParagraphs, ReferencedParagraphs, EvidenceBasedResponse] = generate_counter(
            submission=submission,
            understood=understood,
            client=client,
            settings=settings,
            span_attrs={
                "motion": submission.motion,
                "student_side": submission.student_side.value,
                "agent_side": ("con" if submission.student_side.value == "pro" else "pro"),
                "format": submission.requested_format.value,
            },
        )
        print("[counter] done")
    except Exception as e:
        print("[error]", str(e))
        raise

    if isinstance(result, PointsResponse):
        for i, cp in enumerate(result.points, start=1):
            print(f"{i}. {cp.point}")
            if cp.support:
                print(f"   - {cp.support}")
        return

    if isinstance(result, RebuttalParagraphs):
        for para in result.paragraphs:
            print(f"\n{para}\n")
        return

    # ReferencedParagraphs or EvidenceBasedResponse
    for para in result.paragraphs:
        print(f"\n{para.text}")
        if para.references:
            print("References:")
            for ref in para.references:
                if hasattr(ref, 'supporting_claim') and ref.supporting_claim:
                    # EvidenceBasedResponse format
                    print(f"- {ref.url}")
                    print(f"  Claim: {ref.supporting_claim}")
                elif hasattr(ref, 'title') and ref.title:
                    print(f"- {ref.title}: {ref.url}")
                else:
                    print(f"- {ref.url}")


if __name__ == "__main__":
    main()
