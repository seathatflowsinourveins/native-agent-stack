def is_allowed(age, has_permit):
    if age >= 18:
        return True
    return has_permit
