from model.tutor import TutorContent, Subject, Topic

user_mapping: dict[str, int] = {}


def add_user(user_id: str, thread_id: int):
    user_mapping[user_id] = thread_id


def get_next_thread_id() -> int:
    if len(user_mapping) == 0:
        return 1
    else:
        return max(user_mapping.values()) + 1


def get_thread_id(user_id: str):
    if user_id in user_mapping:
        return user_mapping[user_id]
    else:
        thread_id = get_next_thread_id()
        add_user(user_id, thread_id)
        return thread_id


def get_user_id(thread_id: int):
    for user_id, thread in user_mapping.items():
        if thread == thread_id:
            return user_id


def default_tutor_content(user_id: str) -> TutorContent:
    """
    Gets data for seeding agent state.
    :param user_id: Not used for now because it's fake data.
    :return: data for seeding agent state.
    """
    tutor_content = TutorContent(subjects={
        "Pre-Algebra": Subject(
            name="Pre-Algebra",
            topics={
                "Integers": Topic(name="Integers"),
                "Fractions": Topic(name="Fractions"),
                "Decimals": Topic(name="Decimals"),
            }
        ),
        "Algebra": Subject(
            name="Algebra",
            topics={
                "Linear Equations": Topic(name="Linear Equations"),
                "Quadratic Equations": Topic(name="Quadratic Equations"),
                "Exponents": Topic(name="Exponents"),
            }
        ),
        "Geometry": Subject(
            name="Geometry",
            topics={
                "Pythagorean Theorem": Topic(name="Pythagorean Theorem"),
                "Angles": Topic(name="Angles"),
                "Circles": Topic(name="Circles"),
            }
        ),
    })
    return tutor_content
