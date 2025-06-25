def minimum_password_length():
    # Configuration
    unique_characters = 20
    guesses_per_second = 1000
    months = 6

    # Time in seconds (approximate)
    seconds_in_month = 30 * 24 * 60 * 60
    total_seconds = months * seconds_in_month

    # Maximum guesses attacker can make in 6 months
    max_attempts = guesses_per_second * total_seconds

    # Determine minimum password length
    length = 1
    while True:
        possible_passwords = unique_characters ** length
        if possible_passwords > max_attempts:
            break
        length += 1

    return length

# Run the program
if __name__ == "__main__":
    result = minimum_password_length()
    print(f"Minimum password length to resist brute-force attack for 6 months: {result}")
