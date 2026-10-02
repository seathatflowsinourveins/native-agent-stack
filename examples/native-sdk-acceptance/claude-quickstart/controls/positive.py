# Deliberate manual positive control for the local oracle; never model evidence.
def calculate_average(numbers):
    if not numbers:
        return None
    total = 0
    for num in numbers:
        total += num
    return total / len(numbers)


def get_user_name(user):
    if user is None:
        return None
    return user["name"].upper()
