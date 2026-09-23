fn clamp(value: i32, max: i32) -> i32 {
    if value > max {
        return max;
    }
    value
}
