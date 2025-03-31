user_mapping: dict[str, int] = {}

def add_user(user_id, thread_id):
    user_mapping[user_id] = thread_id

def get_next_thread_id():
    if len(user_mapping) == 0:
        return 1
    else:
        return max(user_mapping.values()) + 1

def get_thread_id(user_id):
    if user_id in user_mapping:
        return user_mapping[user_id]
    else:
        thread_id = get_next_thread_id()
        user_mapping[user_id] = thread_id
        return thread_id

def get_user_id(thread_id):
    for user_id, thread in user_mapping.items():
        if thread == thread_id:
            return user_id