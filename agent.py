

def build_client(settings:Settings) -> Any:
    client = OpenAI(base_url= "https://api.mistral.ai/v1", api_key = setings.mistral_api_key)
    try:
        logfire.instrument_openai()
    except Expection:
        pass
    return instructor.from_openai(client, mode=Mode.JSON)

def opposite_side(side: DebateSide) -> DebateSide:
    return DebateSide.con if side == DebateSide.pro else DebateSide.pro


@span("understand_arguments")
def understand_arguments(submission: StudentSubmission, client: Any, settings: Settings) -> UnderstoodArguments:
    system = (
        "You are a world-class debate analyst. Your job is to accurately understand the student's argument. "
        "Do not argue yet. Identify the core claims and key supporting points succinctly."
    )
    msg_user = (
        "Motion: "
        + submission.motion
        + "\nStudent side: "
        + submission.student_side.value
        + "\nStudent argument:\n"
        + submission.argument_text
    )


    