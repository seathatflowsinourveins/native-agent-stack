def calculate_average(numbers):
    total = 0
    count = 0
    for num in numbers:
        total += num
        count += 1
    if count == 0:
        return 0.0
    return total / count


def get_user_name(user):
    if user is None:
        return ""
    return (user.get("name") or "").upper()
